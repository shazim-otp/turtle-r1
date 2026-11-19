# TURTLE — Autonomous Windows Desktop AI

An autonomous Windows AI desktop assistant operating with full system freedom, zero permission prompts, real-time webcam hand gesture control, and instant voice controls.

---

## 🚀 How to Run Manually

### Option 1: Double-Click Launcher
Double-click:
```bat
run_turtle.bat
```

### Option 2: Run via Terminal
```powershell
.\.venv\Scripts\activate
python main.py
```

---

## 🖐 Hand Gesture Controls (HUD)
Control your Windows desktop using natural hand gestures through your webcam:

| Gesture | Action | Behavior |
| :--- | :--- | :--- |
| **Move Hand / Index Tip** | **Mouse Cursor** | Mirrored & smoothed using Exponential Moving Average |
| **Pinch Index + Thumb** | **Left Click & Drag** | Pinch once to click; hold pinch to select text / drag windows |
| **Pinch Pinky + Thumb** | **Right Click** | Context menus, right-click actions |
| **All Fingers Hold (Fist)** | **Scroll Up / Down** | Curl all fingers together: move hand **Up** to scroll up, move hand **Down** to scroll down |

### Activating Gestures
- **UI Button:** Click **🖐 Gesture Control** in the TURTLE app.
- **Voice / Chat Command:** Ask *"Turtle, activate hand gesture control"*.
- **To Stop:** Click **🛑 Stop Gesture Control** or press **`q`** / **`ESC`** on the HUD window.

---

## 🔊 Text-To-Speech & Instant Stop
- **Instant Stop Button:** Whenever TURTLE speaks, click the **`⏹ Silence Voice`** button.
- **Keyboard Shortcut (`Esc`):** Pressing the **`Esc`** key on your keyboard instantly silences TURTLE at any moment.
- **Voice / Chat Command:** Tell TURTLE *"Stop talking"*, *"Quiet"*, or *"Silence"*.

---

## 🌐 Autonomous Computer Use Engine (MCUE)
TURTLE can autonomously operate your Windows 10 desktop and Google Chrome browser to accomplish multi-step objectives:

### Example Prompts:
- *"Open Chrome, go to LinkedIn, open my profile and improve my entire profile. Rewrite my headline, About, experience, education and project descriptions. Update the relevant sections and verify the changes."*
- *"Open VS Code, locate my project and inspect the backend."*
- *"Open my website dashboard and change the homepage heading."*
- *"Open Windows Settings and navigate to display settings."*

### Reasoning Cycle:
1. **OBSERVE:** Hybrid capture of screen state, active windows, and live browser DOM / accessibility trees.
2. **UNDERSTAND:** Visual and semantic interpretation of visible text, fields, buttons, and loading states.
3. **PLAN:** High-level milestone decomposition.
4. **CHECK PERMISSIONS:** Safe operations proceed automatically; sensitive changes (publishing, profile edits, deletions) request user authorization with proposed diff.
5. **EXECUTE:** Semantic interactions via Playwright (Chrome) and PyAutoGUI / Win32 (Desktop).
6. **VERIFY:** Confirms that updates were actually saved and reflect in the DOM / visual state.
7. **LIVE MONITOR:** Watch current task progress, milestones, current application, and control actions via `[Pause]`, `[Resume]`, and `[Stop Task]`.

---

## 🎨 Aesthetic & Design
- **Color Theme:** Cybernetic **Deep Blue & Radiant Mint** (`#060d19` & `#00f5b8`).
- **Animated Arc Core:** Dynamic rotating energy rings and status-responsive glow.
- **Glassmorphic HUD:** Telemetry badges (CPU, RAM, Battery), quick action cards, and clean chat bubbles.

---

## ⚡ Autonomous Freedom Mode
- **Zero Permission Prompts:** Carries out tasks directly without interrupting modal dialogs.
- **PowerShell & System Execution:** Full command access (`run_command` / `run_powershell`).
- **Universal App Launcher:** Launch any app, program, or registered file directly (`open_app`).
- **Vision Screen Inspection:** Instant desktop visual analysis via Groq vision AI (`analyze_screen`).
- **Voice & Persona:** Articulate, polite, responsive desktop AI assistant.
