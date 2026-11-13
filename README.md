================================================================================

                         FULL PROJECT DESCRIPTION
================================================================================

# TURTLE — Autonomous Windows Desktop AI Assistant

TURTLE is a next-generation local Windows desktop AI assistant built in Python. Designed with a J.A.R.V.I.S.-style autonomous mindset, TURTLE executes multi-step system workflows with complete freedom and zero permission prompts. It combines vision, voice, system automation, and contactless webcam hand gesture control in a futuristic Deep Blue & Radiant Mint holographic HUD interface.

---

## 🌟 Key Features

### 1. ⚡ Full Autonomy & Zero Permission Friction
- Operates in autonomous execution mode by default.
- Executes commands, scripts, file operations, and application controls directly without interrupting modal confirmation dialogs.
- Multi-step execution loop: plans, chains tools sequentially, and confirms outcomes succinctly.

### 2. 🖐 Contactless Webcam Hand Gesture Mouse Control
- Built with Google MediaPipe Tasks and OpenCV.
- High-precision, zero-latency C-level Windows mouse integration (`ctypes.windll.user32`).
- Smooth pointer movement with Exponential Moving Average (EMA) smoothing and margin clamping.
- Gesture Breakdown:
  * Hand Movement: Direct cursor steering in mirror mode.
  * Index + Thumb Pinch: Left-click and continuous drag-and-drop.
  * Pinky + Thumb Pinch: Right-click context menus (debounced).
  * All Fingers Hold (Fist): Natural vertical scrolling (Hand Up = Scroll Up, Hand Down = Scroll Down).
- Live holographic HUD camera window with real-time skeleton overlay, status badges, and FPS counter.

### 3. 🎙 Voice Input & Speech Feedback with Instant Cutoff
- Voice Recognition: Local, offline audio transcription using Faster-Whisper (CPU-optimized, VAD filtering).
- Vocal Output: High-fidelity speech generation using Microsoft Edge TTS (British RyanNeural voice).
- Instant Silence Controls:
  * Dedicated "⏹ Silence Voice" UI button that lights up crimson during speech.
  * Keyboard shortcut: Press `Esc` anytime to instantly kill audio playback.
  * Voice / chat command: Say "Turtle, stop talking" or "Silence".

### 4. 👁 Visual Desktop Inspection (Screen Vision AI)
- One-click desktop screen capture and compression.
- Visual inspection powered by Groq Vision (`qwen/qwen3.8-27b`).
- Accurately identifies open windows, active tasks, error messages, code, and UI elements.

### 5. 🛠 Deep Windows System Control
- Arbitrary PowerShell & Command execution (`run_command` / `run_powershell`).
- Universal application launcher (`open_app`): launches any executable, game, or URI protocol (Chrome, Spotify, Discord, VS Code, Steam, Settings, etc.).
- Process Management: Close and terminate apps by process name (`close_app`).
- File System Operations: Read, write, append, search, and folder creation anywhere on disk.
- Media & Audio Control: Volume up/down, mute/unmute, play/pause.
- Input Simulation: Direct text typing (`type_text`) and global hotkeys (`press_hotkey` e.g., `['win', 'd']`, `['ctrl', 'c']`).

### 6. 🎨 Cybernetic Blue & Mint HUD GUI
- Modern glassmorphic interface styled in Deep Midnight Ocean (`#060d19`) and Luminous Mint (`#00f5b8`).
- Animated Arc Reactor holographic visualizer: 30 FPS concentric rotating rings, tech ticks, and dynamic pulse reacting to agent state (Idle, Listening, Processing, Speaking, Gesture).
- Real-time live telemetry pills monitoring CPU usage, RAM utilization, and Battery status.
- Structured chat log with clean glass message bubbles.

---

## 🛠 Tech Stack

- Language: Python 3.11
- GUI Framework: PySide6 (Qt for Python)
- LLM & Vision Provider: Groq API (`qwen/qwen3.8-27b`)
- Computer Vision & Gestures: MediaPipe 1.2+ Hand Landmarker, OpenCV (cv2)
- Audio & Speech: Faster-Whisper, SoundDevice, Edge-TTS, Pygame Mixer
- Automation & OS: PyAutoGUI, ctypes User32 API, psutil

---

## 🚀 Quick Start Guide

### Prerequisites
- Windows 10/11 64-bit
- Python 3.11
- Webcam (for hand gesture control)
- Microphone and speakers (for voice control)
- Groq API Key (free from https://console.groq.com/keys)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/TURTLE_AI_Desktop_Agent.git
   cd TURTLE_AI_Desktop_Agent
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure your API key in `.env`:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL=qwen/qwen3.8-27b
   VISION_MODEL=qwen/qwen3.8-27b
   AUTONOMOUS_MODE=true
   WHISPER_MODEL=base
   WHISPER_DEVICE=cpu
   WHISPER_COMPUTE=int8
   TTS_VOICE=en-GB-RyanNeural
   ```

4. Launch TURTLE:
   - Double-click `run_turtle.bat`
   - Or run via terminal:
     ```bash
     python main.py
     ```

---

## 💡 Example Prompts & Commands

- "Check my PC vitals and tell me what is consuming memory."
- "Open Chrome and search for quantum computing breakthroughs."
- "Activate hand gesture control."
- "Create a new folder named Project_Turtle in Documents."
- "Inspect my screen and tell me if there is an error in my code."
- "Turn up the volume and play music on Spotify."
- "Silence voice."
- "Minimize all windows and launch Notepad."

---

## 📄 License
This project is open-source under the MIT License.

