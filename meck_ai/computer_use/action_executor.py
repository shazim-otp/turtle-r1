import time
from typing import Dict, Any, Tuple
from .permission_manager import PermissionManager
from .browser_controller import BrowserController
from .desktop_controller import DesktopController


class ActionExecutor:
    """Validates, authorizes, and dispatches concrete actions to Browser or Desktop controllers."""

    def __init__(self, browser: BrowserController, desktop: DesktopController, permissions: PermissionManager):
        self.browser = browser
        self.desktop = desktop
        self.permissions = permissions

    def execute(self, action_name: str, params: Dict[str, Any], context_summary: str = "") -> Dict[str, Any]:
        """Validate permissions and execute action safely."""
        # 1. Permission check
        authorized, reason = self.permissions.authorize_action(action_name, params, context_summary)
        if not authorized:
            return {"success": False, "action": action_name, "error": f"Authorization denied: {reason}"}

        # 2. Dispatch
        try:
            # --- Browser Actions ---
            if action_name == "browser_goto":
                url = params.get("url", "")
                if not self.browser.is_running:
                    self.browser.start()
                res = self.browser.navigate(url)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            elif action_name == "browser_click":
                target = params.get("selector") or params.get("target") or params.get("text", "")
                by_text = params.get("by_text", False)
                res = self.browser.click(target, by_text=by_text)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            elif action_name == "browser_type":
                target = params.get("selector") or params.get("target", "")
                text = params.get("text", "")
                clear_first = params.get("clear_first", True)
                res = self.browser.type_text(target, text, clear_first=clear_first)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            elif action_name == "browser_scroll":
                direction = params.get("direction", "down")
                amount = int(params.get("amount", 500))
                res = self.browser.scroll(direction=direction, amount=amount)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            elif action_name == "browser_press_key":
                key = params.get("key", "Enter")
                res = self.browser.press_key(key)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            # --- Desktop Actions ---
            elif action_name == "desktop_launch":
                app_name = params.get("app_name", "")
                res = self.desktop.launch_app(app_name)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            elif action_name == "desktop_click":
                x = params.get("x")
                y = params.get("y")
                button = params.get("button", "left")
                clicks = int(params.get("clicks", 1))
                res = self.desktop.click(x=x, y=y, button=button, clicks=clicks)
                return {"success": True, "action": action_name, "details": res}

            elif action_name == "desktop_type":
                text = params.get("text", "")
                res = self.desktop.type_text(text)
                return {"success": True, "action": action_name, "details": res}

            elif action_name == "desktop_hotkey":
                keys = params.get("keys", [])
                if isinstance(keys, str):
                    keys = [k.strip() for k in keys.split("+")]
                res = self.desktop.press_hotkey(*keys)
                return {"success": True, "action": action_name, "details": res}

            elif action_name == "desktop_focus_window":
                query = params.get("title", "")
                res = self.desktop.focus_window(query)
                return {"success": res.get("success", False), "action": action_name, "details": res}

            elif action_name == "wait":
                secs = min(15.0, float(params.get("seconds", 2.0)))
                time.sleep(secs)
                return {"success": True, "action": action_name, "waited": secs}

            else:
                return {"success": False, "action": action_name, "error": f"Unsupported action type: {action_name}"}

        except Exception as e:
            return {"success": False, "action": action_name, "error": str(e)}

