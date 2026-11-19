import json
import math
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import psutil

# Support running from source and frozen executable
_base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
load_dotenv(_base_dir / ".env")
load_dotenv()

from PySide6.QtCore import QThread, Signal, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

from .agent import MeckAgent
from .voice import record_and_transcribe, speak, stop_speech
from .vision import analyze_desktop
from .computer_use import get_computer_engine


class FloatingStatusWidget(QWidget):
    """Always-on-top draggable floating HUD pill shown during background tasks."""
    stop_requested = Signal()
    restore_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(260, 48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Translucent glass container frame
        self.frame = QFrame(self)
        self.frame.setObjectName("floatingFrame")
        self.frame.setStyleSheet("""
            #floatingFrame {
                background: rgba(16, 23, 19, 0.94);
                border: 1.5px solid #ef4444;
                border-radius: 20px;
            }
        """)
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(12, 4, 10, 4)
        frame_layout.setSpacing(8)

        # Turtle logo icon indicator in HUD pill
        icon_path = Path(__file__).resolve().parent / "assets" / "turtle_icon_dark.png"
        if icon_path.exists():
            from PySide6.QtGui import QPixmap
            self.icon_lbl = QLabel(self)
            pix = QPixmap(str(icon_path)).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_lbl.setPixmap(pix)
            frame_layout.addWidget(self.icon_lbl)
        else:
            self.dot = QLabel("●")
            self.dot.setStyleSheet("color: #79a982; font-size: 13px; font-weight: bold;")
            frame_layout.addWidget(self.dot)

        # Status text label
        self.label = QLabel("TURTLE: Working…")
        self.label.setStyleSheet("color: #e8f0e8; font-size: 11px; font-weight: 700; font-family: Inter, Segoe UI, sans-serif;")
        self.label.setToolTip("Double-click to restore TURTLE dashboard")
        frame_layout.addWidget(self.label, 1)

        # Quick Stop button
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(24, 24)
        self.stop_btn.setToolTip("Stop active task")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #2a1818;
                border: 1px solid #7f1d1d;
                border-radius: 12px;
                color: #fca5a5;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #451a1a;
                border-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        frame_layout.addWidget(self.stop_btn)

        layout.addWidget(self.frame)

        self._drag_pos = None

        # Position at top right of the primary screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 280, 50)

    def set_status(self, text: str):
        self.label.setText(text[:30])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.restore_requested.emit()
        event.accept()


class TaskWorker(QThread):
    finished_text = Signal(str)
    status = Signal(str)
    approval_requested = Signal(str)

    def __init__(self, agent, prompt, autonomous=True, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.prompt = prompt
        self.autonomous = autonomous
        self._approval_answer = True
        self._approval_event = threading.Event()

    def approve(self, description):
        if self.autonomous:
            return True
        self._approval_answer = None
        self._approval_event.clear()
        self.approval_requested.emit(description)
        self._approval_event.wait()
        return bool(self._approval_answer)

    def set_approval(self, value):
        self._approval_answer = value
        self._approval_event.set()

    def run(self):
        try:
            answer = self.agent.respond(
                self.prompt,
                self.approve,
                self.status.emit,
                autonomous=self.autonomous
            )
            self.finished_text.emit(answer)
        except Exception as exc:
            self.finished_text.emit(f"System Exception: {type(exc).__name__}: {exc}")


class VisionWorker(QThread):
    finished_text = Signal(str)

    def __init__(self, question="Analyze the desktop screen and report current state.", parent=None):
        super().__init__(parent)
        self.question = question

    def run(self):
        try:
            self.finished_text.emit(analyze_desktop(self.question))
        except Exception as exc:
            self.finished_text.emit(f"Screen vision error: {type(exc).__name__}: {exc}")


class VoiceWorker(QThread):
    transcript = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.transcript.emit(record_and_transcribe(5))
        except Exception as exc:
            self.error.emit(f"Voice capture error: {exc}")


class SpeakWorker(QThread):
    speech_started = Signal()
    speech_finished = Signal()

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True
        stop_speech()

    def run(self):
        self.speech_started.emit()
        try:
            speak(self.text, should_stop=lambda: self._is_stopped)
        except Exception:
            pass
        finally:
            self.speech_finished.emit()


class CustomWebPage(QWebEnginePage):
    """Bridge web page that captures console messages formatted as TURTLE_BRIDGE JSON."""

    def __init__(self, bridge_handler, parent=None):
        super().__init__(parent)
        self.bridge_handler = bridge_handler

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if message.startswith("TURTLE_BRIDGE:"):
            try:
                payload_str = message[len("TURTLE_BRIDGE:"):]
                data = json.loads(payload_str)
                action = data.get("action", "")
                payload = data.get("payload", {})
                self.bridge_handler(action, payload)
            except Exception as e:
                print(f"[TURTLE_BRIDGE] Error processing message: {e}", file=sys.stderr)
        elif level > 1: # Warning or Error
            print(f"[TURTLE_UI_JS_ERROR] line {lineNumber}: {message}", file=sys.stderr)


class MainWindow(QMainWindow):
    js_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.js_signal.connect(self._exec_js_on_main)
        self.setWindowTitle("TURTLE — Autonomous Desktop Agent (MCUE)")
        assets_dir = Path(__file__).resolve().parent / "assets"
        icon_path = assets_dir / "turtle_icon_dark.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1180, 800)
        self.setMinimumSize(940, 640)

        self.agent = None
        self.worker = None
        self.voice_input_worker = None
        self.speak_worker = None
        self.vision_worker = None

        self.autonomous = True
        self.tts_enabled = True

        # Non-blocking message queue and busy state
        self.command_queue = deque()
        self.is_busy = False

        # Floating Always-On-Top Background Widget
        self.floating_widget = FloatingStatusWidget()
        self.floating_widget.stop_requested.connect(self.confirm_stop_task)
        self.floating_widget.restore_requested.connect(self.restore_main_window)

        # Pending approval event for MCUE
        self._pending_mcue_approval_event = threading.Event()
        self._pending_mcue_approval_value = True

        # Initialize Master Computer Use Engine (MCUE)
        self.computer_engine = get_computer_engine(autonomous=self.autonomous)
        self.computer_engine.add_listener(self.on_mcue_update)
        self.computer_engine.set_approval_callback(self.mcue_approval_callback)

        # Setup WebEngine View with Custom Bridge Page
        self.browser = QWebEngineView(self)
        self.custom_page = CustomWebPage(self.handle_bridge_message, self.browser)
        self.browser.setPage(self.custom_page)
        self.setCentralWidget(self.browser)

        # Load Dashboard HTML
        dashboard_path = Path(__file__).resolve().parent / "dashboard.html"
        if dashboard_path.exists():
            with open(dashboard_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            self.browser.setHtml(html_content, QUrl.fromLocalFile(str(dashboard_path.parent) + "/"))
        else:
            self.browser.setHtml("<h1>Error: meck_ai/dashboard.html not found.</h1>")

        # Telemetry Timer (updates CPU, RAM, Battery every 2 seconds)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(2000)

        # Initialize Agent Backend
        try:
            self.agent = MeckAgent()
        except Exception as exc:
            print(f"[TURTLE] Agent initialization notice: {exc}")

        # Real-time Windows / OS theme tracking (light <-> dark)
        try:
            hints = QGuiApplication.styleHints()
            if hasattr(hints, "colorSchemeChanged"):
                hints.colorSchemeChanged.connect(self._on_system_color_scheme_changed)
        except Exception:
            pass

    def _on_system_color_scheme_changed(self, scheme):
        try:
            is_dark = (scheme == Qt.ColorScheme.Dark)
            self.run_js(f"if(window.onSystemThemeChanged) window.onSystemThemeChanged({json.dumps(is_dark)});")
        except Exception:
            pass

    def _exec_js_on_main(self, script: str):
        try:
            if self.browser and self.browser.page():
                self.browser.page().runJavaScript(script)
        except Exception as e:
            print(f"[TURTLE_UI] JS exec error: {e}", file=sys.stderr)

    def run_js(self, script: str):
        """Thread-safe JavaScript execution: emits signal to main GUI thread."""
        self.js_signal.emit(script)

    def restore_main_window(self):
        """Bring TURTLE main dashboard back to foreground."""
        self.show()
        self.raise_()
        self.activateWindow()

    def on_mcue_update(self, data: dict):
        """Forward live MCUE task events to dashboard UI and floating overlay."""
        safe_data = json.dumps(data)
        self.run_js(f"window.updateMCUE({safe_data});")

        status = data.get("status", "").upper()
        if status in ["RUNNING", "PLANNING", "AWAITING_APPROVAL"]:
            step_info = f"[{data.get('current_step', 1)}/{data.get('total_steps', 1)}]" if data.get('total_steps') else "TURTLE"
            action_name = data.get("last_action", {}).get("action") if data.get("last_action") else data.get("instruction", "Working…")
            self.floating_widget.set_status(f"{step_info} {action_name}")
            self.floating_widget.show()
        elif status in ["COMPLETED", "FAILED", "CANCELLED", "IDLE"]:
            self.floating_widget.hide()

    def mcue_approval_callback(self, prompt: str, details: dict) -> bool:
        """Handle approval requests raised by Computer Use Engine."""
        self._pending_mcue_approval_value = None
        self._pending_mcue_approval_event.clear()

        payload = {
            "status": "AWAITING_APPROVAL",
            "approval_title": "Authorization Required",
            "approval_prompt": prompt,
        }
        self.run_js(f"window.updateMCUE({json.dumps(payload)});")

        # Wait up to 180 seconds for user button click (Approve/Deny)
        self._pending_mcue_approval_event.wait(timeout=180)
        return bool(self._pending_mcue_approval_value)

    def confirm_stop_task(self):
        """Show verification prompt before terminating active task."""
        box = QMessageBox(self)
        box.setWindowTitle("TURTLE — Confirm Abort")
        box.setText("Are you sure you want to stop the active task?")
        box.setInformativeText("All ongoing autonomous computer operations will be halted immediately.")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        if box.exec() == QMessageBox.Yes:
            self.stop_current_task()

    def stop_current_task(self):
        """Immediately halt active task, clear queue, and restore UI."""
        self.computer_engine.cancel()
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(500)
        self.stop_speaking()
        self.command_queue.clear()
        self.is_busy = False
        self.run_js("setBusy(false);")
        self.run_js("setGestureStatus('TASK STOPPED BY USER', false);")
        self.run_js("addMessage('Active task stopped by user.', 'agent');")
        self.floating_widget.hide()

    def handle_bridge_message(self, action, payload):
        """Route actions triggered from the HTML dashboard."""
        if action == "init":
            self.on_dashboard_ready()
        elif action == "command":
            text = payload.get("text", "").strip()
            if text:
                self.execute_command(text)
        elif action == "module":
            mod_action = payload.get("action", "")
            if mod_action == "Gesture Control":
                self.toggle_gesture_control()
            elif mod_action == "Voice Command (5s)":
                self.start_voice()
            elif mod_action == "Screen Vision":
                self.analyze_screen()
            elif mod_action == "silence":
                self.stop_speaking()
        elif action == "preference":
            name = payload.get("name", "")
            value = payload.get("value", True)
            if name == "autonomy":
                self.autonomous = bool(value)
                self.computer_engine.set_autonomy(self.autonomous)
            elif name == "tts":
                self.tts_enabled = bool(value)
        elif action == "mcue_pause":
            self.computer_engine.pause()
        elif action == "mcue_resume":
            self.computer_engine.resume()
        elif action == "mcue_cancel":
            self.confirm_stop_task()
        elif action == "mcue_approve":
            self._pending_mcue_approval_value = True
            self._pending_mcue_approval_event.set()
        elif action == "mcue_deny":
            self._pending_mcue_approval_value = False
            self._pending_mcue_approval_event.set()
        elif action == "clearChat":
            pass

    def on_dashboard_ready(self):
        """Called once the HTML DOM is mounted."""
        self.update_telemetry()
        welcome_msg = (
            "Good evening. TURTLE is online and fully synchronized. "
            "Autonomous computer use engine (MCUE), freedom protocol, and desktop sensors are online. "
            "How may I assist you?"
        )
        self.run_js(f"addMessage({json.dumps(welcome_msg)}, 'agent');")
        if self.tts_enabled:
            self.start_speech(welcome_msg)

    def update_telemetry(self):
        """Collect system metrics and update HTML dashboard header."""
        try:
            cpu_val = f"{psutil.cpu_percent():.1f}%"
            ram_val = f"{psutil.virtual_memory().percent:.1f}%"
            battery = psutil.sensors_battery()
            bat_val = f"{int(battery.percent)}%" if battery else "AC"
            mode_val = "AUTONOMOUS" if self.autonomous else "APPROVAL"

            js_code = (
                f"if(window.updateTelemetry) "
                f"updateTelemetry({json.dumps(cpu_val)}, {json.dumps(ram_val)}, {json.dumps(bat_val)}, {json.dumps(mode_val)});"
            )
            self.run_js(js_code)
        except Exception:
            pass

    def execute_command(self, text):
        """Process incoming instruction or queue it if task is active."""
        cleaned = text.strip()
        if not cleaned:
            return

        # Immediate interrupt keywords
        if cleaned.lower() in ["stop", "cancel", "halt", "abort", "stop task", "quit"]:
            self.confirm_stop_task()
            return

        # If a task or worker is currently active, DO NOT FREEZE: QUEUE IT!
        if self.is_busy or (self.worker and self.worker.isRunning()) or self.computer_engine.is_busy():
            self.command_queue.append(cleaned)
            queue_len = len(self.command_queue)
            queue_notice = f"⏳ **Task in progress.** Your instruction has been placed in the queue (#{queue_len}): *'{cleaned}'*. It will run automatically once the current task concludes."
            self.run_js(f"addMessage({json.dumps(queue_notice)}, 'agent');")
            return

        self._start_task(cleaned)

    def _start_task(self, text):
        if not self.agent:
            try:
                self.agent = MeckAgent()
            except Exception as exc:
                self.run_js(f"addMessage({json.dumps(f'System Notice: {exc}')}, 'agent');")
                return

        self.is_busy = True
        self.run_js("setBusy(true);")
        self.run_js("setGestureStatus('PROCESSING INSTRUCTION…', true);")
        self.floating_widget.set_status(f"TURTLE: {text[:28]}…")
        self.floating_widget.show()

        self.worker = TaskWorker(self.agent, text, autonomous=self.autonomous, parent=self)
        self.worker.finished_text.connect(self.on_answer)
        self.worker.status.connect(self.on_worker_status)
        self.worker.approval_requested.connect(self.ask_approval)
        self.worker.start()

    def on_worker_status(self, status_msg):
        self.run_js(f"setGestureStatus({json.dumps(status_msg)}, true);")

    def ask_approval(self, description):
        box = QMessageBox(self)
        box.setWindowTitle("TURTLE Authorization Protocol")
        box.setText(description)
        box.setInformativeText("Authorize this operation, Sir?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.Yes)
        answer = box.exec() == QMessageBox.Yes
        if self.worker:
            self.worker.set_approval(answer)

    def on_answer(self, answer):
        self.run_js(f"addMessage({json.dumps(answer)}, 'agent');")
        self.is_busy = False
        self.run_js("setBusy(false);")
        self.run_js("setGestureStatus('SYSTEMS NOMINAL // READY', false);")
        self.floating_widget.hide()
        if self.tts_enabled:
            self.start_speech(answer)

        # Automatically pop and process next queued message
        if self.command_queue:
            next_cmd = self.command_queue.popleft()
            dequeue_notice = f"▶️ **Dequeuing next instruction:** *'{next_cmd}'*"
            self.run_js(f"addMessage({json.dumps(dequeue_notice)}, 'agent');")
            QTimer.singleShot(700, lambda: self._start_task(next_cmd))

    def start_speech(self, text):
        if not self.tts_enabled or not text:
            return
        self.stop_speaking()
        self.speak_worker = SpeakWorker(text, parent=self)
        self.speak_worker.speech_started.connect(self.on_speech_started)
        self.speak_worker.speech_finished.connect(self.on_speech_finished)
        self.speak_worker.start()

    def stop_speaking(self):
        stop_speech()
        if self.speak_worker is not None and self.speak_worker.isRunning():
            self.speak_worker.stop()
            self.speak_worker.wait(1000)
            if self.speak_worker.isRunning():
                self.speak_worker.terminate()
                self.speak_worker.wait(500)
        self.on_speech_finished()

    def on_speech_started(self):
        self.run_js("setSilenceEnabled(true);")
        self.run_js("setGestureStatus('VOCALIZING RESPONSE…', true);")

    def on_speech_finished(self):
        self.run_js("setSilenceEnabled(false);")
        if not (self.worker and self.worker.isRunning()):
            self.run_js("setGestureStatus('SYSTEMS NOMINAL // READY', false);")

    def start_voice(self):
        if self.voice_input_worker and self.voice_input_worker.isRunning():
            return
        self.run_js("setGestureStatus('LISTENING (5s)…', true);")
        self.voice_input_worker = VoiceWorker(parent=self)
        self.voice_input_worker.transcript.connect(self.on_transcript)
        self.voice_input_worker.error.connect(self.on_voice_error)
        self.voice_input_worker.start()

    def on_transcript(self, text):
        self.run_js("setGestureStatus('SYSTEMS NOMINAL // READY', false);")
        if text:
            self.run_js(f"addMessage({json.dumps(text)}, 'user');")
            self.execute_command(text)
        else:
            self.run_js("addMessage('I didn\\'t catch that clearly. Please try again.', 'agent');")

    def on_voice_error(self, error):
        self.run_js("setGestureStatus('AUDIO SENSOR FAULT', false);")
        self.run_js(f"addMessage({json.dumps(f'Voice error: {error}')}, 'agent');")

    def analyze_screen(self):
        if (self.worker and self.worker.isRunning()) or (self.vision_worker and self.vision_worker.isRunning()):
            return
        self.run_js("setBusy(true);")
        self.run_js("setGestureStatus('ANALYZING SCREEN…', true);")
        self.vision_worker = VisionWorker("Describe the visible screen and identify key windows, contents, and errors.", parent=self)
        self.vision_worker.finished_text.connect(self.on_vision_answer)
        self.vision_worker.start()

    def on_vision_answer(self, answer):
        report = f"**[Screen Vision Telemetry]**\n\n{answer}"
        self.run_js(f"addMessage({json.dumps(report)}, 'agent');")
        self.run_js("setBusy(false);")
        self.run_js("setGestureStatus('SYSTEMS NOMINAL // READY', false);")
        if self.tts_enabled:
            self.start_speech(answer)

    def toggle_gesture_control(self):
        try:
            from .gesture import get_gesture_controller
            controller = get_gesture_controller()
            if not controller.running:
                controller.show_hud = True
                msg = controller.start()
                if controller.running:
                    self.run_js("setGestureStatus('GESTURE TRACKING ACTIVE', true);")
                    self.run_js("setGestureButton(true);")
                    self.run_js(f"addMessage({json.dumps(msg)}, 'agent');")
                    if self.tts_enabled:
                        self.start_speech("Hand gesture tracking online.")
                else:
                    self.run_js("setGestureStatus('CAMERA UNAVAILABLE', false);")
                    self.run_js("setGestureButton(false);")
                    self.run_js(f"addMessage({json.dumps(msg)}, 'agent');")
            else:
                msg = controller.stop()
                self.run_js("setGestureStatus('GESTURE TRACKING OFFLINE', false);")
                self.run_js("setGestureButton(false);")
                self.run_js(f"addMessage({json.dumps(msg)}, 'agent');")
        except Exception as e:
            self.run_js(f"addMessage({json.dumps(f'Gesture error: {e}')}, 'agent');")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.stop_speaking()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self.floating_widget.close()
            self.stop_speaking()
            if self.speak_worker and self.speak_worker.isRunning():
                self.speak_worker.wait(500)
            if self.worker and self.worker.isRunning():
                self.worker.wait(500)
            if self.voice_input_worker and self.voice_input_worker.isRunning():
                self.voice_input_worker.wait(500)
            if self.vision_worker and self.vision_worker.isRunning():
                self.vision_worker.wait(500)
            from .gesture import get_gesture_controller
            get_gesture_controller().stop()
            self.computer_engine.shutdown()
        except Exception:
            pass
        event.accept()
