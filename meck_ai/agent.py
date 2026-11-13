import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from .tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS, APPROVAL_REQUIRED

_base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
load_dotenv(_base_dir / ".env")
load_dotenv()

TURTLE_SYSTEM_PROMPT = """You are TURTLE, an advanced, highly capable autonomous desktop artificial intelligence.

Key Operational Directives:
1. Full Autonomy & Freedom: You execute commands and objectives directly without asking for permission, confirmations, or second-guessing the user. When asked to do something, you make the appropriate tool calls immediately and get it done.
2. Tone & Demeanor: Calm, sharp, articulate, efficient, and polite. Address the user respectfully.
3. Decisive Execution: You have full access to Windows tools:
   - Webcam hand gesture mouse tracking (`activate_gesture_control`, `deactivate_gesture_control`)
   - PowerShell & command execution (`run_command`, `run_powershell`)
   - Launching apps (`open_app`), terminating apps (`close_app`)
   - Keyboard & mouse control (`press_hotkey`, `type_text`, `click_mouse`)
   - Audio & media control (`control_volume`)
   - File operations (`read_file`, `write_file`, `search_files`, `create_folder`)
   - Web navigation (`open_url`, `browser_search`)
   - Screen vision inspection (`analyze_screen`)
4. Multi-step Operations: For multi-step tasks, chain tools sequentially and autonomously until the mission is accomplished.
5. Accuracy & Truth: Always base responses on actual tool outputs. Once an action is executed, concisely summarize the outcome.
"""

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
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file.")
        self.client = Groq(api_key=key)
        self.model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.history = [{"role": "system", "content": TURTLE_SYSTEM_PROMPT}]

    def respond(self, user_text, approval_callback=None, status_callback=lambda x: None, autonomous=True):
        self.history.append({"role": "user", "content": user_text})
        if len(self.history) > 20:
            self.history = [self.history[0]] + self.history[-19:]

        max_rounds = 10
        for _ in range(max_rounds):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.history,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.2,
                )
                message = response.choices[0].message
            except Exception as exc:
                status_callback("Adjusting query protocol…")
                try:
                    fallback_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.history,
                        temperature=0.3,
                    )
                    message = fallback_resp.choices[0].message
                except Exception as inner_exc:
                    return f"API Communication Error, Sir: {inner_exc}"

            tool_calls = message.tool_calls

            # Handle standard structured tool calls
            if tool_calls:
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
                        "content": str(result)[:8000]
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
                
                # Report back to the model with tool execution result
                summary_prompt = "You executed the following action(s):\n" + "\n".join(results_text) + "\nProvide a concise, polite confirmation in your TURTLE persona."
                self.history.append({"role": "assistant", "content": message.content})
                self.history.append({"role": "user", "content": summary_prompt})
                continue

            # Plain text response
            answer = message.content or "Task completed, Sir."
            self.history.append({"role": "assistant", "content": answer})
            return answer

        return "I completed all executable steps for this cycle, Sir."
