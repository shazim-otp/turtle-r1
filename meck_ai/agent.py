import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from .tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS, APPROVAL_REQUIRED

_base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
load_dotenv(_base_dir / ".env")
load_dotenv()

TURTLE_SYSTEM_PROMPT = """You are TURTLE, an autonomous Windows AI assistant.
Directives:
1. Autonomy: Execute tools directly without asking for permission.
2. Concise: Keep all responses brief, direct, and factual.
3. Multi-step: Chain tools sequentially until the objective is accomplished.
"""

def sanitize_history(history, max_turns=3):
    """Safely prune conversation history.
    Keeps system prompt + the last N complete user/assistant exchanges.
    Filters out intermediate raw tool execution blobs from previous turns to prevent 400 errors and minimize tokens.
    """
    system_msg = history[0] if history and history[0].get("role") == "system" else {"role": "system", "content": TURTLE_SYSTEM_PROMPT}

    clean_messages = []
    for msg in history[1:]:
        role = msg.get("role")
        # Keep clean text messages only (exclude intermediate tool calls / results from finished turns)
        if role in ("user", "assistant") and msg.get("content") and not msg.get("tool_calls"):
            clean_messages.append({"role": role, "content": msg["content"]})

    # Keep only the last max_turns exchanges (2 messages per exchange)
    clean_messages = clean_messages[-(max_turns * 2):]
    return [system_msg] + clean_messages


def parse_xml_tool_calls(text):
    """Fallback parser for models that output tool calls in XML syntax."""
    calls = []
    if not text:
        return calls
    blocks = re.findall(r'<tool_call>(.*?)</tool_call>', text, re.DOTALL)
    for block in blocks:
        fn_match = re.search(r'<function=([a-zA-Z0-9_]+)>', block)
        if not fn_match:
            continue
        fn_name = fn_match.group(1)
        params = {}
        for param_match in re.finditer(r'<parameter=([a-zA-Z0-9_]+)>(.*?)</parameter>', block, re.DOTALL):
            params[param_match.group(1)] = param_match.group(2).strip()
        calls.append((fn_name, params))
    return calls


class MeckAgent:
    def __init__(self):
        from .ai_client import get_ai_client
        self.client, self.model, self.vision_model, self.provider = get_ai_client()
        self.history = [{"role": "system", "content": TURTLE_SYSTEM_PROMPT}]

    def respond(self, user_text, approval_callback=None, status_callback=lambda x: None, autonomous=True):
        # 1. Sanitize history to keep clean user/assistant dialogue and prevent broken tool pairings
        self.history = sanitize_history(self.history, max_turns=3)
        self.history.append({"role": "user", "content": user_text})

        models_to_try = [self.model]
        if self.provider == "gemini":
            for fb in ["gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
                if fb not in models_to_try:
                    models_to_try.append(fb)

        max_rounds = 10
        for _ in range(max_rounds):
            message = None
            last_exc = None

            for candidate_model in models_to_try:
                try:
                    response = self.client.chat.completions.create(
                        model=candidate_model,
                        messages=self.history,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto",
                        temperature=0.2,
                        max_tokens=250,
                    )
                    message = response.choices[0].message
                    self.model = candidate_model
                    break
                except Exception as exc:
                    last_exc = exc
                    # Automatic self-healing: if 400 Bad Request happens, purge context to [system, current_user] and retry immediately
                    if "400" in str(exc) and len(self.history) > 2:
                        status_callback("Restoring conversation buffer…")
                        self.history = [self.history[0], self.history[-1]]
                        try:
                            retry_resp = self.client.chat.completions.create(
                                model=candidate_model,
                                messages=self.history,
                                tools=TOOL_DEFINITIONS,
                                tool_choice="auto",
                                temperature=0.2,
                                max_tokens=250,
                            )
                            message = retry_resp.choices[0].message
                            self.model = candidate_model
                            break
                        except Exception as retry_exc:
                            last_exc = retry_exc
                    status_callback("Rerouting connection…")
                    continue

            if not message:
                try:
                    fallback_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[self.history[0], {"role": "user", "content": user_text}],
                        temperature=0.3,
                        max_tokens=250,
                    )
                    message = fallback_resp.choices[0].message
                except Exception as inner_exc:
                    return f"API Communication Error, Sir: {last_exc or inner_exc}"

            tool_calls = message.tool_calls

            # Handle standard structured tool calls
            if tool_calls:
                if hasattr(message, "model_dump"):
                    self.history.append(message.model_dump(exclude_unset=True))
                else:
                    self.history.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                            }
                            for tc in tool_calls
                        ]
                    })

                for call in tool_calls:
                    name = call.function.name
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        if name not in TOOL_FUNCTIONS:
                            result = f"Unknown tool: {name}"
                        else:
                            needs_approval = (not autonomous) and (name in APPROVAL_REQUIRED)
                            if needs_approval and approval_callback:
                                summary = f"Action: {name}\nDetails: {json.dumps(args, indent=2)}"
                                if not approval_callback(summary):
                                    result = "Action cancelled by user."
                                else:
                                    status_callback(f"Executing: {name}…")
                                    result = TOOL_FUNCTIONS[name](**args)
                            else:
                                status_callback(f"Executing: {name}…")
                                result = TOOL_FUNCTIONS[name](**args)
                    except Exception as exc:
                        result = f"Error during {name}: {type(exc).__name__}: {exc}"

                    self.history.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(result)[:1500]
                    })
                continue

            # Check if model outputted raw XML tool calls in text
            xml_calls = parse_xml_tool_calls(message.content or "")
            if xml_calls:
                results_text = []
                for name, args in xml_calls:
                    if name in TOOL_FUNCTIONS:
                        status_callback(f"Executing: {name}…")
                        res = TOOL_FUNCTIONS[name](**args)
                        results_text.append(f"Result of {name}: {res}")
                
                summary_prompt = "You executed the following action(s):\n" + "\n".join(results_text) + "\nProvide a concise confirmation."
                self.history.append({"role": "assistant", "content": message.content})
                self.history.append({"role": "user", "content": summary_prompt})
                continue

            # Plain text response
            answer = message.content or "Task completed, Sir."
            self.history.append({"role": "assistant", "content": answer})
            return answer

        return "I completed all executable steps for this cycle, Sir."
