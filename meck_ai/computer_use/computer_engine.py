import threading
from typing import Dict, Any, Optional, Callable

from .task_manager import TaskManager, TaskStatus
from .permission_manager import PermissionManager
from .computer_agent import ComputerAgent


class ComputerUseEngine:
    """Master Entry Point and Coordinator for the MECK Autonomous Computer Use Engine (MCUE)."""

    def __init__(self, autonomous: bool = True):
        self.task_manager = TaskManager()
        self.permission_manager = PermissionManager(autonomous=autonomous)
        self.agent = ComputerAgent(self.task_manager, self.permission_manager)
        self._worker_thread: Optional[threading.Thread] = None
        self._last_result: Optional[Dict[str, Any]] = None

    def set_autonomy(self, autonomous: bool):
        self.permission_manager.set_autonomy(autonomous)

    def set_approval_callback(self, callback: Callable[[str, Dict[str, Any]], bool]):
        self.permission_manager.set_approval_callback(callback)

    def add_listener(self, listener: Callable[[Dict[str, Any]], None]):
        self.task_manager.add_listener(listener)

    def is_busy(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def pause(self):
        self.task_manager.pause()

    def resume(self):
        self.task_manager.resume()

    def cancel(self):
        self.task_manager.cancel()

    def execute_task(self, instruction: str) -> Dict[str, Any]:
        """Run task synchronously."""
        return self.agent.run_task(instruction)

    def execute_task_async(
        self,
        instruction: str,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> threading.Thread:
        """Run task asynchronously in background thread."""
        def _target():
            res = self.agent.run_task(instruction)
            self._last_result = res
            if on_finished:
                on_finished(res)

        self._worker_thread = threading.Thread(target=_target, daemon=True)
        self._worker_thread.start()
        return self._worker_thread

    def shutdown(self):
        """Cleanly close browser and release all resources."""
        self.cancel()
        try:
            self.agent.browser.close()
        except Exception:
            pass


_global_engine: Optional[ComputerUseEngine] = None


def get_computer_engine(autonomous: bool = True) -> ComputerUseEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = ComputerUseEngine(autonomous=autonomous)
    return _global_engine

