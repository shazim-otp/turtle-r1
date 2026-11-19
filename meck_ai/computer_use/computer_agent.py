import json
import os
import re
import time
from typing import Dict, Any, Optional, Callable

try:
    from ..ai_client import get_ai_client
except ImportError:
    from meck_ai.ai_client import get_ai_client

from .task_manager import TaskManager, TaskStatus
from .permission_manager import PermissionManager
from .screen_observer import ScreenObserver
from .vision_engine import VisionEngine
from .accessibility_engine import AccessibilityEngine
from .browser_controller import BrowserController
from .desktop_controller import DesktopController
from .action_planner import ActionPlanner
from .action_executor import ActionExecutor
from .action_verifier import ActionVerifier


AGENT_PROMPT = """You are the MECK Autonomous Computer Use Engine (MCUE).
Your mission is to operate the user's Windows 10 desktop and Google Chrome browser to achieve this objective:
"{objective}"

CURRENT ENVIRONMENT STATE:
• Active Application: {active_app}
• Current Browser URL: {current_url}
• Current Page Title: {page_title}
• Current Milestone Step: {current_step}

INTERACTIVE ACCESSIBILITY ELEMENTS:
{elements_summary}

VISUAL OBSERVATION:
{visual_summary}

PREVIOUS ACTIONS & OUTCOMES:
{action_history}

OPERATIONAL DIRECTIVES:
1. Always prefer semantic elements ([B1], [T1], [L1]) over blind coordinate clicking.
2. If modifying a section (e.g. LinkedIn About, headline, experience), first inspect the text, then click Edit, update content, and verify.
3. For profile modifications, prepare well-structured, professional copy that elevates the user's credentials.
4. If the task is finished, set "is_task_complete": true and provide a thorough summary.

AVAILABLE ACTIONS:
- "browser_goto": {{"url": "https://..."}}
- "browser_click": {{"selector": "#id or [attr]" or "target": "button name/text", "by_text": true/false}}
- "browser_type": {{"selector": "#id or input name", "text": "content to type", "clear_first": true}}
- "browser_scroll": {{"direction": "down"|"up", "amount": 500}}
- "browser_press_key": {{"key": "Enter"|"Tab"|"Escape"}}
- "desktop_launch": {{"app_name": "notepad"|"chrome"|"code"|etc.}}
- "desktop_click": {{"x": 100, "y": 200, "button": "left"|"right"}}
- "desktop_type": {{"text": "content"}}
- "desktop_hotkey": {{"keys": ["ctrl", "s"]}}
- "desktop_focus_window": {{"title": "window title"}}
- "wait": {{"seconds": 2}}

Respond ONLY with valid JSON:
{{
  "thought": "Internal reasoning about current state and what to do next",
  "action": "action_name",
  "params": {{ ... }},
  "expected_outcome": "What state change is expected",
  "milestone_completed": "Title of step if one was finished, else null",
  "is_task_complete": false,
  "completion_summary": ""
}}
"""


class ComputerAgent:
    """The Autonomous Computer Use Agent implementing the Observe-Understand-Plan-Act-Verify cycle."""

    def __init__(
        self,
        task_manager: TaskManager,
        permission_manager: PermissionManager,
        client: Optional[Any] = None,
        model: Optional[str] = None
    ):
        self.task_manager = task_manager
        self.permission_manager = permission_manager

        if client:
            self.client = client
            self.model = model or os.getenv("GEMINI_MODEL") or os.getenv("GROQ_MODEL", "gemini-3.5-flash")
            self.provider = "gemini"
        else:
            try:
                c, m, _, prov = get_ai_client()
                self.client = c
                self.model = model or m
                self.provider = prov
            except Exception:
                self.client = None
                self.model = model or "gemini-3.5-flash"
                self.provider = "gemini"

        # Core Subsystems
        self.observer = ScreenObserver()
        self.vision = VisionEngine(client=self.client)
        self.accessibility = AccessibilityEngine()
        self.browser = BrowserController()
        self.desktop = DesktopController()
        self.planner = ActionPlanner(client=self.client, model=self.model)
        self.executor = ActionExecutor(self.browser, self.desktop, self.permission_manager)
        self.verifier = ActionVerifier(self.browser, self.observer, self.vision)

    def run_task(self, instruction: str) -> Dict[str, Any]:
        """Execute autonomous computer use reasoning loop until completion, failure, or cancellation."""
        task_id = self.task_manager.start_new_task(instruction)

        # 1. INITIAL OBSERVATION & PLANNING
        win_info = self.observer.get_active_window_info()
        self.task_manager.update_environment(app=win_info.get("title", "Desktop"))

        initial_plan = self.planner.create_plan(instruction, current_context=win_info)
        self.task_manager.set_plan(initial_plan)

        step_counter = 0

        while step_counter < self.task_manager.max_steps:
            step_counter += 1

            # Check cancellation and pause
            if self.task_manager.is_cancelled():
                return {"success": False, "status": "CANCELLED", "message": "Task cancelled by user."}

            self.task_manager.wait_if_paused()
            if self.task_manager.is_cancelled():
                return {"success": False, "status": "CANCELLED", "message": "Task cancelled by user."}

            # -------------------------------------------------------------
            # STEP 1: OBSERVE & UNDERSTAND
            # -------------------------------------------------------------
            win_info = self.observer.get_active_window_info()
            active_app = win_info.get("title", "Desktop")

            # Check if browser is running and focused
            browser_elements_summary = ""
            current_url = ""
            page_title = ""

            if self.browser.is_running:
                try:
                    page_info = self.browser.get_page_info()
                    current_url = page_info.get("url", "")
                    page_title = page_info.get("title", "")
                    self.task_manager.update_environment(app="Google Chrome", url=current_url, tab=page_title)

                    raw_el = self.browser.extract_interactive_elements()
                    parsed = self.accessibility.parse_browser_elements(raw_el)
                    browser_elements_summary = parsed.get("summary_text", "")
                except Exception:
                    pass

            if not browser_elements_summary:
                # Desktop accessibility fallback
                parsed_desk = self.accessibility.parse_desktop_elements(active_app)
                browser_elements_summary = parsed_desk.get("summary_text", "")

            # Take screenshot
            _, shot_path = self.observer.capture_screen()
            self.task_manager.update_environment(screenshot_path=shot_path)

            # Visual analysis
            last_action_desc = ""
            if self.task_manager.action_history:
                last_act = self.task_manager.action_history[-1]
                last_action_desc = f"{last_act['action']}({last_act['params']})"

            visual_info = self.vision.inspect_screen_state(shot_path, instruction, last_action=last_action_desc)
            visual_summary = visual_info.get("visible_summary", "Desktop visible.")

            # Loop detection
            state_sig = f"{current_url}|{active_app}|{visual_summary[:50]}"
            if self.task_manager.check_loop(state_sig):
                # Suggest recovery
                visual_summary += " [NOTE: Repetitive state detected. Try scrolling or refreshing.]"

            # -------------------------------------------------------------
            # STEP 2: DECIDE NEXT ACTION (AI BRAIN)
            # -------------------------------------------------------------
            history_summary = []
            for h in self.task_manager.action_history[-4:]:
                history_summary.append(f"• {h['action']}({h['params']}) -> {h['result'][:100]}")
            history_text = "\n".join(history_summary) if history_summary else "None yet."

            current_milestone = (
                self.task_manager.pending_steps[0]
                if self.task_manager.pending_steps
                else "Finalizing task"
            )

            prompt = AGENT_PROMPT.format(
                objective=instruction,
                active_app=active_app,
                current_url=current_url,
                page_title=page_title,
                current_step=current_milestone,
                elements_summary=browser_elements_summary or "(No interactive elements extracted)",
                visual_summary=visual_summary,
                action_history=history_text,
            )

            models_to_try = [self.model]
            if self.provider == "gemini":
                for cand in ["gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
                    if cand not in models_to_try:
                        models_to_try.append(cand)

            decision = None
            last_err = None
            for m in models_to_try:
                try:
                    resp = self.client.chat.completions.create(
                        model=m,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=350,
                    )
                    raw_decision = (resp.choices[0].message.content or "").strip()
                    cleaned_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_decision, flags=re.DOTALL).strip()
                    decision = json.loads(cleaned_json)
                    self.model = m
                    break
                except Exception as e:
                    last_err = e
                    time.sleep(0.3)
                    continue

            if decision is None:
                self.task_manager.fail(f"Agent reasoning error: {last_err}")
                return {"success": False, "status": "FAILED", "error": str(last_err)}

            # -------------------------------------------------------------
            # STEP 3: CHECK COMPLETION
            # -------------------------------------------------------------
            if decision.get("is_task_complete", False):
                summary = decision.get("completion_summary", "Objective successfully completed.")
                self.task_manager.complete(summary)
                return {"success": True, "status": "COMPLETED", "summary": summary}

            action_name = decision.get("action", "")
            params = decision.get("params", {})
            expected = decision.get("expected_outcome", "")
            thought = decision.get("thought", "")

            if not action_name:
                continue

            # -------------------------------------------------------------
            # STEP 4: EXECUTE ACTION
            # -------------------------------------------------------------
            exec_res = self.executor.execute(action_name, params, context_summary=thought)

            # -------------------------------------------------------------
            # STEP 5: OBSERVE AGAIN & VERIFY
            # -------------------------------------------------------------
            verified, verify_reason = self.verifier.verify(action_name, params, exec_res, expected_outcome=expected)
            self.task_manager.record_action(action_name, params, str(exec_res.get("details", exec_res)), verified=verified)

            # Advance milestone if reported
            milestone = decision.get("milestone_completed")
            if milestone:
                self.task_manager.advance_step(str(milestone))

            time.sleep(0.5)

        self.task_manager.fail("Task reached maximum allowable steps without concluding.")
        return {"success": False, "status": "FAILED", "error": "Maximum steps exceeded."}
