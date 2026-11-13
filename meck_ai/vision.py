import base64
import io
import os
from PIL import Image, ImageGrab
import pyautogui
from groq import Groq

def analyze_desktop(question="Describe what is visible on my screen and help me with it."):
    """Capture desktop screenshot, downscale, and analyze using Groq vision."""
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

    # Downscale and compress to keep within token limits and latency budget
    image.thumbnail((1600, 1000))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=75, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return "GROQ_API_KEY is not configured in .env."

    client = Groq(api_key=groq_key)
    # Use vision capable model
    model = os.getenv("VISION_MODEL", "qwen/qwen3.8-27b")

    try:
        response = client.chat.completions.create(
            model=model,
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
            max_completion_tokens=1000,
        )
        return response.choices[0].message.content or "No visual details could be discerned."
    except Exception as exc:
        return f"Visual analysis error: {type(exc).__name__}: {exc}"
