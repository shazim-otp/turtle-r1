import re
from typing import Callable, Optional, Dict, Any, Tuple


class PermissionManager:
    """Manages autonomy, safety checks, and approval thresholds for Computer Use actions."""

    # Actions that ALWAYS require explicit approval regardless of autonomy mode
    CRITICAL_ACTIONS = {
        "send_message",
        "publish_post",
        "submit_payment",
        "purchase",
        "delete_file",
        "delete_content",
        "modify_security_settings",
        "install_software",
        "admin_operation",
    }

    # Actions requiring approval in APPROVAL mode, or when modifying public profile / important forms
    SENSITIVE_ACTIONS = {
        "save_profile",
        "update_profile",
        "submit_form",
        "overwrite_file",
        "click_save",
        "post_comment",
    }

    # Patterns indicating high-risk intent in button texts or descriptions
    CRITICAL_PATTERNS = [
        r"\b(buy|purchase|pay|checkout|order)\b",
        r"\b(delete|remove|erase|destroy|drop)\b",
        r"\b(send|publish|post|tweet|broadcast)\b",
        r"\b(password|credential|two-factor|2fa|api[ _-]?key)\b",
    ]

    def __init__(self, autonomous: bool = True, approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None):
        self.autonomous = autonomous
        self.approval_callback = approval_callback

    def set_autonomy(self, autonomous: bool):
        self.autonomous = autonomous

    def set_approval_callback(self, callback: Callable[[str, Dict[str, Any]], bool]):
        self.approval_callback = callback

    def is_action_sensitive(self, action_name: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Determine if an action or its parameters touch sensitive/critical resources."""
        action_name_lower = action_name.lower().strip()

        # Direct name check
        if action_name_lower in self.CRITICAL_ACTIONS:
            return True, f"Action '{action_name}' is classified as Critical."

        if action_name_lower in self.SENSITIVE_ACTIONS:
            return True, f"Action '{action_name}' modifies persistent or public state."

        # Parameter string scan (e.g. clicking 'Save' on a profile or clicking 'Delete')
        param_text = " ".join(str(v) for v in params.values()).lower()

        # Check for profile save or public update
        if "save" in param_text and any(k in param_text for k in ["profile", "headline", "about", "experience", "publish"]):
            return True, "Modifying and saving public profile contents."

        for pattern in self.CRITICAL_PATTERNS:
            if re.search(pattern, param_text, re.IGNORECASE):
                return True, f"Detected potentially high-impact operation ({pattern})."

        return False, "Standard operational action."

    def request_approval(self, action_name: str, params: Dict[str, Any], context_summary: str = "") -> bool:
        """Prompt user or execute approval callback for sensitive actions."""
        if not self.approval_callback:
            # If no callback is wired, default safe behavior: block critical
            is_sensitive, _ = self.is_action_sensitive(action_name, params)
            return not is_sensitive

        details = {
            "action": action_name,
            "params": params,
            "context": context_summary,
            "autonomous_mode": self.autonomous,
        }
        prompt = (
            f"Operation Authorization Required:\n"
            f"• Action: {action_name}\n"
            f"• Target / Content: {params.get('text') or params.get('selector') or params.get('url') or 'N/A'}\n"
            f"• Summary: {context_summary or 'Persistent change requested.'}"
        )
        return self.approval_callback(prompt, details)

    def authorize_action(self, action_name: str, params: Dict[str, Any], context: str = "") -> Tuple[bool, str]:
        """Check if action is authorized to proceed immediately or requires user sign-off."""
        is_sensitive, reason = self.is_action_sensitive(action_name, params)

        # In Approval Mode, any sensitive action requires approval
        if not self.autonomous or is_sensitive:
            approved = self.request_approval(action_name, params, context or reason)
            if approved:
                return True, "Authorized by user."
            return False, f"Action declined or cancelled by user ({reason})."

        # Safe ordinary action in autonomous mode
        return True, "Authorized under autonomous freedom protocol."

