import ctypes
import time
from typing import Dict, Any, List, Optional, Tuple
import pyautogui
from ..tools import open_app as tools_open_app

user32 = ctypes.windll.user32


class DesktopController:
    """Controls native Windows desktop: mouse movement, clicks, keyboard typing, hotkeys, and window switching."""

    def __init__(self):
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
        self.screen_width, self.screen_height = pyautogui.size()

    def move_to(self, x: int, y: int, duration: float = 0.2) -> Dict[str, Any]:
        cx = max(0, min(self.screen_width - 1, x))
        cy = max(0, min(self.screen_height - 1, y))
        pyautogui.moveTo(cx, cy, duration=duration)
        return {"success": True, "x": cx, "y": cy}

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        if x is not None and y is not None:
            self.move_to(x, y, duration=0.15)
        pyautogui.click(button=button, clicks=clicks)
        return {"success": True, "button": button, "clicks": clicks}

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x, y, button="left", clicks=2)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x, y, button="right", clicks=1)

    def type_text(self, text: str, interval: float = 0.01) -> Dict[str, Any]:
        pyautogui.write(text, interval=interval)
        return {"success": True, "text_length": len(text)}

    def press_hotkey(self, *keys: str) -> Dict[str, Any]:
        pyautogui.hotkey(*keys)
        return {"success": True, "hotkey": "+".join(keys)}

    def press_key(self, key: str) -> Dict[str, Any]:
        pyautogui.press(key)
        return {"success": True, "key": key}

    def scroll(self, clicks: int = -3) -> Dict[str, Any]:
        pyautogui.scroll(clicks)
        return {"success": True, "clicks": clicks}

    def launch_app(self, app_name: str) -> Dict[str, Any]:
        result = tools_open_app(app_name)
        time.sleep(1.0)
        return {"success": "Error" not in result, "output": result}

    def focus_window(self, title_query: str) -> Dict[str, Any]:
        """Find and bring window matching title_query to the foreground."""
        target_hwnd = None

        def enum_cb(hwnd, extra):
            nonlocal target_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if title_query.lower() in buff.value.lower():
                        target_hwnd = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        try:
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception:
            pass

        if target_hwnd:
            user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(target_hwnd)
            time.sleep(0.3)
            return {"success": True, "hwnd": target_hwnd, "query": title_query}

        return {"success": False, "error": f"No window found matching '{title_query}'"}

