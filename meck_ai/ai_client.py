import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
load_dotenv(_base_dir / ".env")
load_dotenv()


def get_ai_client(provider: str = None):
    """Factory that returns an initialized client and model name based on provider configuration.
    
    Supports:
    - Google Gemini: via OpenAI-compatible endpoint with 'gemini-3.5-flash'
    - Groq: via Groq SDK with 'qwen/qwen3.8-27b'
    """
    configured_provider = (provider or os.getenv("AI_PROVIDER", "")).strip().lower()

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key == "YOUR_GEMINI_API_KEY_HERE":
        gemini_key = ""

    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    # Determine provider: explicitly 'gemini' or gemini_key provided
    if configured_provider == "gemini" or (gemini_key and not groq_key) or (configured_provider != "groq" and gemini_key):
        if not gemini_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Please open .env and add your Gemini API key."
            )
        from openai import OpenAI
        client = OpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
        vision_model = os.getenv("GEMINI_VISION_MODEL", "gemini-flash-lite-latest")
        return client, model, vision_model, "gemini"

    # Default to Groq if configured or key available
    if not groq_key and not gemini_key:
        raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured in your .env file.")

    from groq import Groq
    client = Groq(api_key=groq_key)
    model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    vision_model = os.getenv("VISION_MODEL", "qwen/qwen3.8-27b")
    return client, model, vision_model, "groq"
