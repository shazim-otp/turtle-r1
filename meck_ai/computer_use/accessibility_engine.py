import re
from typing import Dict, Any, List, Optional


class AccessibilityEngine:
    """Extracts, indexes, and normalizes semantic accessibility elements from browser DOM and native Windows UI."""

    def __init__(self):
        pass

    def parse_browser_elements(self, raw_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert raw Playwright element descriptors into clean, indexed semantic elements."""
        indexed: Dict[str, Dict[str, Any]] = {}
        formatted_lines: List[str] = []

        counter = 1
        for el in raw_elements:
            tag = el.get("tag", "").lower()
            role = el.get("role", tag).lower()
            text = (el.get("text") or el.get("aria_label") or el.get("placeholder") or "").strip()
            name = (el.get("name") or "").strip()
            value = (el.get("value") or "").strip()
            selector = el.get("selector", "")
            is_visible = el.get("is_visible", True)

            if not is_visible:
                continue

            # Assign concise ref code (e.g. B1 for button, T1 for input/textarea, L1 for link)
            prefix = "E"
            if "button" in role or tag == "button" or el.get("type") == "submit":
                prefix = "B"
            elif "link" in role or tag == "a":
                prefix = "L"
            elif "textbox" in role or tag in ["input", "textarea"]:
                prefix = "T"
            elif "checkbox" in role:
                prefix = "C"
            elif "heading" in role or tag in ["h1", "h2", "h3", "h4"]:
                prefix = "H"

            ref_id = f"[{prefix}{counter}]"
            counter += 1

            descriptor = text or name or value or f"Unnamed {role}"
            # Truncate overly long text
            if len(descriptor) > 80:
                descriptor = descriptor[:77] + "…"

            extra_info = []
            if value and prefix == "T":
                extra_info.append(f'val="{value[:40]}"')
            if el.get("placeholder"):
                extra_info.append(f'placeholder="{el.get("placeholder")}"')

            extra_str = f" ({', '.join(extra_info)})" if extra_info else ""
            line = f"{ref_id} {role.upper()}: \"{descriptor}\"{extra_str}"
            formatted_lines.append(line)

            indexed[ref_id] = {
                "ref_id": ref_id,
                "role": role,
                "tag": tag,
                "text": text,
                "name": name,
                "value": value,
                "selector": selector,
                "box": el.get("box"),
            }

        return {
            "summary_text": "\n".join(formatted_lines[:75]),  # Keep top 75 most relevant elements to respect token budget
            "indexed_elements": indexed,
            "total_count": len(indexed),
        }

    def parse_desktop_elements(self, window_title: str) -> Dict[str, Any]:
        """Query native Windows UI Automation for interactive controls in the active window."""
        try:
            import pywinauto
            from pywinauto import Desktop

            app = Desktop(backend="uia")
            # Find window matching title
            window = None
            for w in app.windows():
                if window_title.lower() in w.window_text().lower():
                    window = w
                    break

            if not window:
                return {"summary_text": f"No native UIA handles found for '{window_title}'.", "indexed_elements": {}}

            indexed: Dict[str, Dict[str, Any]] = {}
            lines: List[str] = []
            counter = 1

            # Iterate child controls
            for child in window.descendants():
                try:
                    c_type = child.element_info.control_type or "Control"
                    c_text = child.window_text().strip()
                    if not c_text:
                        continue

                    ref_id = f"[W{counter}]"
                    counter += 1
                    line = f"{ref_id} {c_type.upper()}: \"{c_text[:60]}\""
                    lines.append(line)

                    rect = child.rectangle()
                    indexed[ref_id] = {
                        "ref_id": ref_id,
                        "type": c_type,
                        "text": c_text,
                        "center": ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2),
                    }
                    if counter > 50:
                        break
                except Exception:
                    continue

            return {
                "summary_text": "\n".join(lines[:50]),
                "indexed_elements": indexed,
                "total_count": len(indexed),
            }
        except Exception as e:
            return {
                "summary_text": f"Native desktop UI inspection: active window '{window_title}'. (UIA notice: {e})",
                "indexed_elements": {},
                "total_count": 0,
            }

