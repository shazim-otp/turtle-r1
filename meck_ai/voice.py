import asyncio
import os
import tempfile
import threading
from pathlib import Path

import edge_tts
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import pygame

_model = None
_stop_speech_event = threading.Event()

def record_and_transcribe(seconds=5):
    global _model
    rate = 16000
    audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    write(wav_path, rate, audio)
    try:
        if _model is None:
            _model = WhisperModel(
                os.getenv("WHISPER_MODEL", "tiny"),
                device=os.getenv("WHISPER_DEVICE", "cpu"),
                compute_type=os.getenv("WHISPER_COMPUTE", "int8"),
            )
        segments, _ = _model.transcribe(wav_path, beam_size=3, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        Path(wav_path).unlink(missing_ok=True)

async def _speak_async(text, output_path):
    voice = os.getenv("TTS_VOICE", "en-GB-RyanNeural")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def stop_speech():
    """Immediately stop speech generation and audio playback."""
    global _stop_speech_event
    _stop_speech_event.set()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except Exception:
        pass

def speak(text, should_stop=None):
    """Play TTS audio for the given text with instant cancellation support."""
    global _stop_speech_event
    _stop_speech_event.clear()

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        if _stop_speech_event.is_set() or (should_stop and should_stop()):
            return

        asyncio.run(_speak_async(text[:1500], path))

        if _stop_speech_event.is_set() or (should_stop and should_stop()):
            return

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if _stop_speech_event.is_set() or (should_stop and should_stop()):
                pygame.mixer.music.stop()
                break
            pygame.time.wait(50)
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        Path(path).unlink(missing_ok=True)
