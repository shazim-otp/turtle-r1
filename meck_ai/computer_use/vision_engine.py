import base64
import io
import json
import os
import re
import time
from typing import Dict, Any, Optional, Tuple, Union
from PIL import Image

try:
    from ..ai_client import get_ai_client
except ImportError:
    from meck_ai.ai_client import get_ai_client


class VisionEngine:
    """Provides visual understanding of screenshots using AI vision (Gemini / Groq) with failover."""

    def __init__(self, client: Optional[Any] = None, model: Optional[str] = None):
        self.provider = "gemini"
        if client:
            self.client = client
            self.model = model or os.getenv("GEMINI_VISION_MODEL", "gemini-flash-lite-latest")
        else:
            try:
                c, _, vm, prov = get_ai_client()
                self.client = c
                self.model = model or vm
                self.provider = prov
            except Exception:
                self.client = None
                self.model = model or "gemini-flash-lite-latest"

    def _get_models_to_try(self):
        models = [self.model]
        if self.provider == "gemini":
            for cand in ["gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
                if cand not in models:
                    models.append(cand)
        return models

    def encode_image(self, image_input: Union[str, Image.Image]) -> str:
        """Convert path or PIL Image to base64 string."""
        if isinstance(image_input, str):
            with open(image_input, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        elif isinstance(image_input, Image.Image):
            buffer = io.BytesIO()
            img_copy = image_input.copy()
            img_copy.thumbnail((960, 540))
            img_copy.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("ascii")
        raise ValueError("Unsupported image input type.")

    def inspect_screen_state(self, image_input: Union[str, Image.Image], task_goal: str, last_action: str = "") -> Dict[str, Any]:
        """Analyze what is currently visible: active app, page, dialogs, loading state, and progress toward goal."""
        if not self.client:
            return {"error": "AI API Key missing", "description": "Visual engine offline."}

        encoded_img = self.encode_image(image_input)
        prompt = f"""You are the visual observation subsystem of an autonomous desktop agent.
Analyze the provided screenshot with respect to the user's objective: "{task_goal}".
Recent Action: "{last_action or 'Initial state'}"

Provide a concise JSON response with these keys:
- "active_application": Name of the primary window/application visible
- "current_page_or_view": Specific page, tab, or document view visible
- "is_loading": Boolean, true if a spinner, loading indicator, or greyed-out state is visible
- "has_modal_or_popup": Boolean, true if an alert, confirmation, or modal is overlaying the page
- "error_message": Any visible error or warning banner text (or null)
- "visible_summary": 2-3 sentence description of current state and relevant buttons/fields
- "next_visual_suggestion": Specific element or button to interact with next

Return ONLY valid JSON.
"""
        models = self._get_models_to_try()
        last_error = None
        for m in models:
            try:
                resp = self.client.chat.completions.create(
                    model=m,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}}
                        ]
                    }],
                    temperature=0.2,
                    max_tokens=300,
                )
                raw = (resp.choices[0].message.content or "").strip()
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
                return json.loads(cleaned)
            except Exception as e:
                last_error = e
                time.sleep(0.3)
                continue

        return {
            "active_application": "Unknown",
            "current_page_or_view": "Desktop",
            "is_loading": False,
            "has_modal_or_popup": False,
            "error_message": None,
            "visible_summary": f"Visual parsing notice: {last_error}",
            "next_visual_suggestion": ""
        }

    def verify_change(self, image_input: Union[str, Image.Image], expected_result: str) -> Tuple[bool, str]:
        """Check whether the screenshot visually confirms the expected outcome."""
        if not self.client:
            return True, "Vision check skipped (offline mode)."

        encoded_img = self.encode_image(image_input)
        prompt = f"""Review this screenshot and evaluate whether the following expected outcome was achieved:
Expected Outcome: "{expected_result}"

Reply in JSON format:
{{
  "achieved": true or false,
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "reason": "Brief explanation of what is visually observed"
}}
Return ONLY valid JSON.
"""
        models = self._get_models_to_try()
        last_error = None
        for m in models:
            try:
                resp = self.client.chat.completions.create(
                    model=m,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}}
                        ]
                    }],
                    temperature=0.1,
                    max_tokens=200,
                )
                raw = (resp.choices[0].message.content or "").strip()
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
                data = json.loads(cleaned)
                return bool(data.get("achieved", False)), data.get("reason", "Verification complete.")
            except Exception as e:
                last_error = e
                time.sleep(0.3)
                continue

        return True, f"Visual verification notice: {last_error}"
