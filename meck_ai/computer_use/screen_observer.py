import ctypes
from ctypes import wintypes
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageGrab
import pyautogui

user32 = ctypes.windll.user32


class ScreenObserver:
    """Observes the physical Windows desktop, active windows, and visual state."""

    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()

    def capture_screen(self, output_path: Optional[str] = None, max_dim: Tuple[int, int] = (1600, 1000)) -> Tuple[Image.Image, str]:
        """Capture full screen image and save to a temporary or designated file."""
        try:
            image = pyautogui.screenshot()
        except Exception:
            try:
                image = ImageGrab.grab(all_screens=True)
            except Exception as e:
                # Fallback blank
                image = Image.new("RGB", (self.screen_width, self.screen_height), color=(30, 30, 30))

        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            output_path = tmp.name
            tmp.close()

        # Scale down for vision tokens
        img_copy = image.copy()
        img_copy.thumbnail(max_dim)
        img_copy.convert("RGB").save(output_path, format="JPEG", quality=75, optimize=True)

        return img_copy, output_path

    def get_active_window_info(self) -> Dict[str, Any]:
        """Get the title, process ID, and coordinates of the currently focused window."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"title": "Desktop / Taskbar", "hwnd": 0, "rect": (0, 0, self.screen_width, self.screen_height)}

        # Get Title length
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value or "Untitled Window"

        # Get Rect
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        return {
            "title": title,
            "hwnd": hwnd,
            "rect": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": max(0, rect.right - rect.left),
                "height": max(0, rect.bottom - rect.top),
            }
        }

    def list_visible_windows(self) -> List[Dict[str, Any]]:
        """List titles of visible, non-empty top-level windows."""
        windows = []

        def enum_windows_callback(hwnd, extra):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title and title not in ["Program Manager", "Default IME", "MSCTFIME UI"]:
                        windows.append({"hwnd": hwnd, "title": title})
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return windows

    def get_screen_dimensions(self) -> Tuple[int, int]:
        return pyautogui.size()

