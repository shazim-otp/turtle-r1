import time
import uuid
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
import threading


class TaskStatus(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskManager:
    """Tracks task state, execution plan, progress, and controls (pause, resume, cancel)."""

    def __init__(self, max_steps: int = 35, step_timeout: float = 60.0):
        self.max_steps = max_steps
        self.step_timeout = step_timeout

        self.task_id: str = ""
        self.instruction: str = ""
        self.status: TaskStatus = TaskStatus.IDLE
        self.plan: List[Dict[str, Any]] = []
        self.current_step_index: int = 0
        self.completed_steps: List[Dict[str, Any]] = []
        self.pending_steps: List[Dict[str, Any]] = []

        self.current_app: str = "Desktop"
        self.current_url: str = ""
        self.current_tab: str = ""
        self.last_screenshot_path: Optional[str] = None

        self.action_history: List[Dict[str, Any]] = []
        self.errors: List[str] = []

        self._cancel_requested = threading.Event()
        self._pause_requested = threading.Event()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

        # Loop detection tracker
        self._state_history: List[str] = []

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to live task progress updates."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify(self, event_type: str, message: str = "", extra: Optional[Dict[str, Any]] = None):
        snapshot = self.get_summary()
        snapshot["event_type"] = event_type
        snapshot["event_message"] = message
        if extra:
            snapshot.update(extra)
        for listener in self._listeners:
            try:
                listener(snapshot)
            except Exception:
                pass

    def start_new_task(self, instruction: str) -> str:
        """Initialize a new autonomous task."""
        self.task_id = str(uuid.uuid4())[:8]
        self.instruction = instruction
        self.status = TaskStatus.PLANNING
        self.plan = []
        self.current_step_index = 0
        self.completed_steps = []
        self.pending_steps = []
        self.action_history = []
        self.errors = []
        self._state_history = []
        self._cancel_requested.clear()
        self._pause_requested.clear()

        self._notify("task_started", f"Starting task: {instruction}")
        return self.task_id

    def set_plan(self, steps: List[str]):
        """Set or update the planned execution milestones."""
        self.plan = [{"index": idx + 1, "title": s, "completed": False} for idx, s in enumerate(steps)]
        self.pending_steps = list(self.plan)
        self.completed_steps = []
        self.current_step_index = 0
        self.status = TaskStatus.RUNNING
        self._notify("plan_created", f"Created plan with {len(steps)} steps.")

    def advance_step(self, step_title: str):
        """Mark step progress."""
        for step in self.plan:
            if step["title"] == step_title or step["index"] == self.current_step_index + 1:
                step["completed"] = True
                if step not in self.completed_steps:
                    self.completed_steps.append(step)
                if step in self.pending_steps:
                    self.pending_steps.remove(step)
                self.current_step_index += 1
                break
        self._notify("step_advanced", f"Completed step: {step_title}")

    def record_action(self, action_name: str, params: Dict[str, Any], result: str, verified: bool = True):
        entry = {
            "timestamp": time.time(),
            "step": self.current_step_index + 1,
            "action": action_name,
            "params": params,
            "result": str(result)[:300],
            "verified": verified,
        }
        self.action_history.append(entry)
        self._notify("action_executed", f"Executed: {action_name}", {"action_entry": entry})

    def update_environment(self, app: str = "", url: str = "", tab: str = "", screenshot_path: str = ""):
        if app:
            self.current_app = app
        if url:
            self.current_url = url
        if tab:
            self.current_tab = tab
        if screenshot_path:
            self.last_screenshot_path = screenshot_path
        self._notify("environment_updated")

    def check_loop(self, current_signature: str) -> bool:
        """Detect if agent is stuck repeating identical states (> 3 times)."""
        self._state_history.append(current_signature)
        if len(self._state_history) > 12:
            self._state_history = self._state_history[-12:]
        return self._state_history.count(current_signature) >= 3

    def pause(self):
        self._pause_requested.set()
        self.status = TaskStatus.PAUSED
        self._notify("task_paused", "Task execution paused by user.")

    def resume(self):
        self._pause_requested.clear()
        self.status = TaskStatus.RUNNING
        self._notify("task_resumed", "Task execution resumed.")

    def cancel(self):
        self._cancel_requested.set()
        self.status = TaskStatus.CANCELLED
        self._notify("task_cancelled", "Task execution cancelled by user.")

    def complete(self, summary: str = "Task successfully completed."):
        self.status = TaskStatus.COMPLETED
        self._notify("task_completed", summary)

    def fail(self, error: str):
        self.status = TaskStatus.FAILED
        self.errors.append(error)
        self._notify("task_failed", f"Task failed: {error}")

    def is_cancelled(self) -> bool:
        return self._cancel_requested.is_set()

    def is_paused(self) -> bool:
        return self._pause_requested.is_set()

    def wait_if_paused(self, poll_interval: float = 0.5):
        """Block worker thread while task is in paused state."""
        while self.is_paused() and not self.is_cancelled():
            time.sleep(poll_interval)

    def get_summary(self) -> Dict[str, Any]:
        """Return full structured view of task state."""
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "status": self.status.value,
            "current_app": self.current_app,
            "current_url": self.current_url,
            "current_tab": self.current_tab,
            "current_step": self.current_step_index + 1,
            "total_steps": len(self.plan),
            "plan": self.plan,
            "completed_steps": [s["title"] for s in self.completed_steps],
            "pending_steps": [s["title"] for s in self.pending_steps],
            "last_action": self.action_history[-1] if self.action_history else None,
            "errors": self.errors,
            "screenshot": self.last_screenshot_path,
        }

