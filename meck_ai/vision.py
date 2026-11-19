import base64
import io
import os
import time
from PIL import Image, ImageGrab
import pyautogui
from .ai_client import get_ai_client

def analyze_desktop(question="Describe what is visible on my screen and help me with it."):
    """Capture desktop screenshot, downscale, and analyze using AI vision (Gemini or Groq)."""
    image = None
    try:
        image = pyautogui.screenshot()
    except Exception:
        try:
            image = ImageGrab.grab(all_screens=True)
        except Exception as exc:
            return f"Unable to capture desktop screen: {exc}"

    if image is None:
        return "Failed to acquire screen image."

    # Downscale and compress for minimal token usage
    image.thumbnail((960, 540))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    try:
        client, _, vision_model, provider = get_ai_client()
    except Exception as exc:
        return f"AI Client configuration notice: {exc}"

    models = [vision_model]
    if provider == "gemini":
        for cand in ["gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
            if cand not in models:
                models.append(cand)

    last_exc = None
    for m in models:
        try:
            response = client.chat.completions.create(
                model=m,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You are TURTLE, the advanced visual intelligence system. "
                                "Analyze this real-time capture of the user's screen with high precision. "
                                "Identify key windows, active applications, notifications, text, or errors. "
                                f"User inquiry / objective: {question}"
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64," + encoded
                            }
                        },
                    ],
                }],
                temperature=0.2,
                max_tokens=300,
            )
            return response.choices[0].message.content or "No visual details could be discerned."
        except Exception as exc:
            last_exc = exc
            time.sleep(0.4)
            continue

    return f"Visual analysis error: {last_exc}"
