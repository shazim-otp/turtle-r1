import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import psutil

# Support running from source and frozen executable
_base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
load_dotenv(_base_dir / ".env")
load_dotenv()

from PySide6.QtCore import QThread, Signal, Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient,
    QFont, QPainterPath
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QMessageBox, QCheckBox, QFrame,
    QProgressBar, QGraphicsDropShadowEffect
)
from .agent import MeckAgent
from .voice import record_and_transcribe, speak, stop_speech
from .vision import analyze_desktop


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
        self._approval_event = __import__("threading").Event()

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

    def __init__(self, question="Analyze the desktop screen and report current state."):
        super().__init__()
        self.question = question

    def run(self):
        try:
            self.finished_text.emit(analyze_desktop(self.question))
        except Exception as exc:
            self.finished_text.emit(f"Screen vision error: {type(exc).__name__}: {exc}")


class VoiceWorker(QThread):
    transcript = Signal(str)
    error = Signal(str)

    def run(self):
        try:
            self.transcript.emit(record_and_transcribe(5))
        except Exception as exc:
            self.error.emit(f"Voice capture error: {exc}")


class SpeakWorker(QThread):
    speech_started = Signal()
    speech_finished = Signal()

    def __init__(self, text):
        super().__init__()
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


class ArcReactorWidget(QWidget):
    """Futuristic Stark Industries Arc Reactor Holographic Visualizer.
    Renders animated concentric rotating rings, glowing energy core, and dynamic pulse.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(190, 190)
        self.state = "IDLE"  # IDLE, LISTENING, PROCESSING, SPEAKING, GESTURE
        self.angle_outer = 0.0
        self.angle_inner = 0.0
        self.pulse = 0.0
        self.pulse_dir = 1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(33)  # ~30 FPS smooth rendering

    def set_state(self, state):
        self.state = state
        self.update()

    def _animate(self):
        # Rotate outer and inner rings
        speed_mult = 3.5 if self.state in ("PROCESSING", "SPEAKING") else 1.0
        self.angle_outer = (self.angle_outer + 1.2 * speed_mult) % 360
        self.angle_inner = (self.angle_inner - 2.0 * speed_mult) % 360

        # Pulse breathing effect
        step = 0.04 if self.state == "LISTENING" else (0.07 if self.state == "SPEAKING" else 0.02)
        self.pulse += step * self.pulse_dir
        if self.pulse >= 1.0:
            self.pulse = 1.0
            self.pulse_dir = -1
        elif self.pulse <= 0.0:
            self.pulse = 0.0
            self.pulse_dir = 1

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # Color schemes based on TURTLE operational state (Blue & Mint palette)
        if self.state == "LISTENING":
            core_color = QColor(0, 150, 255)       # Electric Blue
            ring_color = QColor(0, 245, 184)       # Mint
        elif self.state == "PROCESSING":
            core_color = QColor(0, 245, 184)       # Mint
            ring_color = QColor(0, 180, 255)       # Sky Blue
        elif self.state == "SPEAKING":
            core_color = QColor(0, 255, 200)       # Bright Mint Cyan
            ring_color = QColor(0, 140, 255)       # Deep Electric Blue
        elif self.state == "GESTURE":
            core_color = QColor(0, 255, 170)       # Emerald Mint
            ring_color = QColor(0, 210, 255)       # Ice Blue
        else:  # IDLE
            core_color = QColor(0, 245, 184)       # Mint Core
            ring_color = QColor(0, 140, 255)       # Deep Ocean Blue Rings

        # 1. Outer Glow Aura
        glow_rad = 85 + self.pulse * 7
        radial = QRadialGradient(cx, cy, glow_rad)
        radial.setColorAt(0.0, QColor(core_color.red(), core_color.green(), core_color.blue(), int(40 + self.pulse * 30)))
        radial.setColorAt(0.6, QColor(core_color.red(), core_color.green(), core_color.blue(), int(15 + self.pulse * 15)))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(radial))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_rad, glow_rad)

        # 2. Outer Segmented Ring
        outer_pen = QPen(QColor(ring_color.red(), ring_color.green(), ring_color.blue(), 180), 2.2)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.NoBrush)
        outer_r = 74
        outer_rect = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)

        # Draw segmented circular arcs (Stark Reactor vents)
        num_segments = 8
        span = 28
        gap = 360 / num_segments
        for i in range(num_segments):
            start_angle = int((self.angle_outer + i * gap) * 16)
            painter.drawArc(outer_rect, start_angle, int(span * 16))

        # 3. Outer Radial Tech Ticks
        tick_pen = QPen(QColor(ring_color.red(), ring_color.green(), ring_color.blue(), 120), 1.2)
        painter.setPen(tick_pen)
        for i in range(24):
            ang = math.radians(self.angle_outer + i * (360 / 24))
            x1 = cx + math.cos(ang) * 65
            y1 = cy + math.sin(ang) * 65
            x2 = cx + math.cos(ang) * 70
            y2 = cy + math.sin(ang) * 70
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # 4. Middle Counter-Rotating Ring
        mid_r = 52
        mid_rect = QRectF(cx - mid_r, cy - mid_r, mid_r * 2, mid_r * 2)
        mid_pen = QPen(QColor(ring_color.red(), ring_color.green(), ring_color.blue(), 210), 1.8)
        painter.setPen(mid_pen)
        num_inner_arcs = 4
        for i in range(num_inner_arcs):
            start_angle = int((self.angle_inner + i * (360 / num_inner_arcs)) * 16)
            painter.drawArc(mid_rect, start_angle, int(50 * 16))

        # 5. Inner Geometric Brackets (Triangular Arc Reactor Bracing)
        bracket_pen = QPen(QColor(core_color.red(), core_color.green(), core_color.blue(), 230), 1.5)
        painter.setPen(bracket_pen)
        tri_r = 38
        for i in range(3):
            ang = math.radians(self.angle_inner * 0.5 + i * 120)
            x_tip = cx + math.cos(ang) * tri_r
            y_tip = cy + math.sin(ang) * tri_r
            ang_left = ang + math.radians(20)
            ang_right = ang - math.radians(20)
            painter.drawLine(QPointF(cx, cy), QPointF(x_tip, y_tip))
            painter.drawLine(QPointF(x_tip, y_tip), QPointF(cx + math.cos(ang_left) * (tri_r - 8), cy + math.sin(ang_left) * (tri_r - 8)))
            painter.drawLine(QPointF(x_tip, y_tip), QPointF(cx + math.cos(ang_right) * (tri_r - 8), cy + math.sin(ang_right) * (tri_r - 8)))

        # 6. Central Energy Core (Hyper-Glowing Center)
        core_r = 20 + self.pulse * 3.5
        core_radial = QRadialGradient(cx, cy, core_r)
        core_radial.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_radial.setColorAt(0.4, QColor(core_color.red(), core_color.green(), core_color.blue(), 220))
        core_radial.setColorAt(0.9, QColor(core_color.red(), core_color.green(), core_color.blue(), 70))
        core_radial.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(core_radial))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TURTLE // Autonomous Desktop AI")
        self.resize(1080, 760)
        self.setMinimumSize(940, 640)

        self.agent = None
        self.worker = None
        self.voice_input_worker = None
        self.speak_worker = None
        self.vision_worker = None

        # Build HUD Interface
        self.init_ui()

        # Telemetry Timer (updates CPU, RAM, Battery every 2 seconds)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(2000)
        self.update_telemetry()

        # Initialize Agent
        try:
            self.agent = MeckAgent()
            self.set_hud_status("ALL SYSTEMS NOMINAL // READY", "IDLE")
            self.append_turtle_message(
                "Good evening. TURTLE is fully synchronized and operational. "
                "Autonomous freedom protocol is engaged — all desktop controls, tools, and sensors are online. "
                "How may I assist you?"
            )
        except Exception as exc:
            self.set_hud_status("SYSTEM INITIALIZATION FAULT", "IDLE")
            self.append_system_pill(f"STARTUP ERROR: {exc}")

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # =========================================================================
        # 1. TOP HEADER // TELEMETRY HUD BAR
        # =========================================================================
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(14, 8, 14, 8)

        # Brand / Logo
        brand_layout = QVBoxLayout()
        brand_title = QLabel("TURTLE")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("AUTONOMOUS DESKTOP AGENT // SYSTEM ONLINE")
        brand_subtitle.setObjectName("brandSubtitle")
        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(brand_subtitle)
        top_bar_layout.addLayout(brand_layout)

        top_bar_layout.addStretch()

        # Telemetry Badges
        self.cpu_pill = QLabel("CPU: --%")
        self.cpu_pill.setObjectName("telemetryPill")
        top_bar_layout.addWidget(self.cpu_pill)

        self.ram_pill = QLabel("RAM: --%")
        self.ram_pill.setObjectName("telemetryPill")
        top_bar_layout.addWidget(self.ram_pill)

        self.bat_pill = QLabel("POWER: --")
        self.bat_pill.setObjectName("telemetryPill")
        top_bar_layout.addWidget(self.bat_pill)

        self.mode_pill = QLabel("MODE: AUTONOMOUS")
        self.mode_pill.setObjectName("telemetryPillActive")
        top_bar_layout.addWidget(self.mode_pill)

        main_layout.addWidget(top_bar)

        # =========================================================================
        # 2. MAIN BODY // LEFT CONTROL NEXUS + RIGHT HOLOGRAPHIC CHAT STREAM
        # =========================================================================
        body_layout = QHBoxLayout()
        body_layout.setSpacing(12)

        # -------------------------------------------------------------------------
        # LEFT PANEL: ARC REACTOR CORE + SYSTEM CONTROLS
        # -------------------------------------------------------------------------
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(12)

        # Visualizer Arc Reactor Widget
        reactor_container = QHBoxLayout()
        reactor_container.addStretch()
        self.arc_reactor = ArcReactorWidget(self)
        reactor_container.addWidget(self.arc_reactor)
        reactor_container.addStretch()
        left_layout.addLayout(reactor_container)

        # Status Badge
        self.status_badge = QLabel("● SYSTEMS INITIALIZING")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.status_badge)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("panelDivider")
        left_layout.addWidget(divider)

        # Action Buttons Section Header
        cmd_header = QLabel("COMMAND MODULES")
        cmd_header.setObjectName("sectionHeader")
        left_layout.addWidget(cmd_header)

        # Gesture Control Button
        self.gesture_button = QPushButton("🖐 Gesture Control")
        self.gesture_button.setObjectName("actionButton")
        self.gesture_button.clicked.connect(self.toggle_gesture_control)
        left_layout.addWidget(self.gesture_button)

        # Screen Vision Button
        self.vision_button = QPushButton("👁 Inspect Screen")
        self.vision_button.setObjectName("actionButton")
        self.vision_button.clicked.connect(self.analyze_screen)
        left_layout.addWidget(self.vision_button)

        # Voice Push-to-Talk Button
        self.voice_button = QPushButton("🎙 Voice Command (5s)")
        self.voice_button.setObjectName("actionButton")
        self.voice_button.clicked.connect(self.start_voice)
        left_layout.addWidget(self.voice_button)

        # Emergency Silence Voice Button
        self.stop_speech_button = QPushButton("⏹ Silence Voice")
        self.stop_speech_button.setObjectName("stopButton")
        self.stop_speech_button.setEnabled(False)
        self.stop_speech_button.setToolTip("Instantly stop voice speech (or press Esc)")
        self.stop_speech_button.clicked.connect(self.stop_speaking)
        left_layout.addWidget(self.stop_speech_button)

        left_layout.addStretch()

        # Toggles
        self.autonomous_check = QCheckBox("⚡ Autonomous Freedom")
        self.autonomous_check.setObjectName("hudCheckBox")
        self.autonomous_check.setChecked(True)
        self.autonomous_check.stateChanged.connect(self.on_autonomous_changed)
        left_layout.addWidget(self.autonomous_check)

        self.speak_check = QCheckBox("🔊 Vocal Responses (TTS)")
        self.speak_check.setObjectName("hudCheckBox")
        self.speak_check.setChecked(True)
        left_layout.addWidget(self.speak_check)

        body_layout.addWidget(left_panel)

        # -------------------------------------------------------------------------
        # RIGHT PANEL: HOLOGRAPHIC CHAT STREAM
        # -------------------------------------------------------------------------
        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        chat_header_layout = QHBoxLayout()
        chat_header = QLabel("TACTICAL COMMUNICATIONS LOG")
        chat_header.setObjectName("sectionHeader")
        chat_header_layout.addWidget(chat_header)
        chat_header_layout.addStretch()

        self.clear_btn = QPushButton("Clear Log")
        self.clear_btn.setObjectName("tinyButton")
        self.clear_btn.clicked.connect(lambda: self.chat.clear())
        chat_header_layout.addWidget(self.clear_btn)
        right_layout.addLayout(chat_header_layout)

        # Chat Terminal Display
        self.chat = QTextEdit()
        self.chat.setObjectName("chatStream")
        self.chat.setReadOnly(True)
        right_layout.addWidget(self.chat, 1)

        body_layout.addWidget(right_panel, 1)
        main_layout.addLayout(body_layout, 1)

        # =========================================================================
        # 3. BOTTOM COMMAND BAR // INPUT + SEND
        # =========================================================================
        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(10)

        # Input Field
        self.input = QLineEdit()
        self.input.setObjectName("commandInput")
        self.input.setPlaceholderText("State your instruction or query for TURTLE (e.g. 'Open Chrome', 'Check my PC status')...")
        self.input.returnPressed.connect(self.send_text)
        bottom_layout.addWidget(self.input, 1)

        # Send Button
        self.send_button = QPushButton("⚡ EXECUTE")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self.send_text)
        bottom_layout.addWidget(self.send_button)

        main_layout.addWidget(bottom_bar)

        # =========================================================================
        # 4. STYLESHEET // SLEEK BLUE & MINT CYBERNETIC THEME
        # =========================================================================
        self.setStyleSheet("""
            QMainWindow {
                background-color: #060d19;
            }
            QWidget {
                color: #d8e8f8;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QFrame#topBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #09152b, stop:1 #0c1c38);
                border: 1px solid #15325b;
                border-radius: 10px;
            }
            QLabel#brandTitle {
                color: #00f5b8;
                font-size: 24px;
                font-weight: 900;
                letter-spacing: 3px;
            }
            QLabel#brandSubtitle {
                color: #4d7ea8;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1.5px;
            }
            QLabel#telemetryPill {
                background: #0a1a33;
                border: 1px solid #183c6d;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
                color: #7ec8f8;
                font-family: 'Consolas', monospace;
            }
            QLabel#telemetryPillActive {
                background: rgba(0, 245, 184, 0.12);
                border: 1px solid #00f5b8;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
                color: #00f5b8;
                font-family: 'Consolas', monospace;
            }
            QFrame#leftPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #081427, stop:1 #060e1d);
                border: 1px solid #15325b;
                border-radius: 12px;
            }
            QFrame#rightPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #081427, stop:1 #060e1d);
                border: 1px solid #15325b;
                border-radius: 12px;
            }
            QLabel#statusBadge {
                background: rgba(0, 245, 184, 0.08);
                border: 1px solid rgba(0, 245, 184, 0.35);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 800;
                color: #00f5b8;
                letter-spacing: 1px;
                font-family: 'Consolas', monospace;
            }
            QFrame#panelDivider {
                border: 0;
                border-top: 1px solid #15325b;
                margin: 4px 0px;
            }
            QLabel#sectionHeader {
                color: #588eb8;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }
            QPushButton#actionButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d2242, stop:1 #112d57);
                border: 1px solid #1b4379;
                border-radius: 8px;
                padding: 10px 14px;
                color: #e2f0fc;
                font-size: 12px;
                font-weight: 700;
                text-align: left;
            }
            QPushButton#actionButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #112e59, stop:1 #163d75);
                border: 1px solid #00f5b8;
                color: #ffffff;
            }
            QPushButton#actionButton:pressed {
                background: #0044aa;
            }
            QPushButton#stopButton {
                background: #101a26;
                border: 1px solid #1c2e42;
                border-radius: 8px;
                padding: 10px 14px;
                color: #556c82;
                font-size: 12px;
                font-weight: 700;
                text-align: left;
            }
            QPushButton#stopButton:enabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #990024, stop:1 #cc0033);
                border: 1px solid #ff3366;
                color: #ffffff;
            }
            QPushButton#stopButton:enabled:hover {
                background: #e60039;
            }
            QPushButton#tinyButton {
                background: transparent;
                border: 1px solid #183863;
                border-radius: 4px;
                padding: 3px 8px;
                color: #6a9cc9;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#tinyButton:hover {
                background: #112a4d;
                border-color: #00f5b8;
                color: #00f5b8;
            }
            QCheckBox#hudCheckBox {
                font-size: 12px;
                font-weight: 600;
                color: #88c8f8;
                spacing: 8px;
            }
            QCheckBox#hudCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #00f5b8;
                background: #081427;
            }
            QCheckBox#hudCheckBox::indicator:checked {
                background: #00f5b8;
            }
            QTextEdit#chatStream {
                background-color: #060c18;
                border: 1px solid #132c52;
                border-radius: 8px;
                padding: 12px;
                color: #e4effa;
                font-size: 13px;
                line-height: 1.6;
            }
            QScrollBar:vertical {
                background: #060c18;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #173863;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00f5b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QFrame#bottomBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #09152b, stop:1 #0c1c38);
                border: 1px solid #15325b;
                border-radius: 10px;
            }
            QLineEdit#commandInput {
                background: #091629;
                border: 1px solid #1c3e6e;
                border-radius: 8px;
                padding: 10px 14px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit#commandInput:focus {
                border: 1px solid #00f5b8;
                background: #0c1c34;
            }
            QPushButton#sendButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00f5b8);
                border: 0;
                border-radius: 8px;
                padding: 10px 22px;
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QPushButton#sendButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066ff, stop:1 #38ef7d);
            }
            QPushButton#sendButton:disabled {
                background: #142236;
                color: #455d78;
            }
        """)

    def update_telemetry(self):
        try:
            cpu = psutil.cpu_percent()
            self.cpu_pill.setText(f"CPU: {cpu}%")
            if cpu > 80:
                self.cpu_pill.setStyleSheet("color: #ff3366; border-color: #ff3366;")
            else:
                self.cpu_pill.setStyleSheet("")

            mem = psutil.virtual_memory()
            self.ram_pill.setText(f"RAM: {mem.percent}%")

            battery = psutil.sensors_battery()
            if battery:
                icon = "⚡" if battery.power_plugged else ""
                self.bat_pill.setText(f"BAT: {battery.percent}% {icon}".strip())
            else:
                self.bat_pill.setText("PWR: AC ONLINE")
        except Exception:
            pass

    def on_autonomous_changed(self):
        is_auto = self.autonomous_check.isChecked()
        if is_auto:
            self.mode_pill.setText("MODE: AUTONOMOUS")
            self.mode_pill.setObjectName("telemetryPillActive")
            self.mode_pill.setStyleSheet("background: rgba(0, 245, 184, 0.12); border: 1px solid #00f5b8; color: #00f5b8;")
        else:
            self.mode_pill.setText("MODE: SUPERVISED")
            self.mode_pill.setStyleSheet("background: #0a1a33; border: 1px solid #183c6d; color: #ffaa00;")

    def set_hud_status(self, text, reactor_state="IDLE"):
        self.status_badge.setText(f"● {text.upper()}")
        self.arc_reactor.set_state(reactor_state)

    def append_user_message(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        html = f"""
        <div style="margin: 8px 0; text-align: right;">
            <div style="display: inline-block; background: #0d2242; border: 1px solid #1a427a; border-radius: 8px; padding: 10px 14px; max-width: 80%; text-align: left;">
                <div style="font-size: 10px; font-weight: 800; color: #7ec8f8; margin-bottom: 4px; font-family: 'Consolas', monospace;">USER // {now}</div>
                <div style="color: #ffffff; font-size: 13px;">{text}</div>
            </div>
        </div>
        """
        self.chat.append(html)

    def append_turtle_message(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        formatted = text.replace("\n", "<br>")
        html = f"""
        <div style="margin: 8px 0; text-align: left;">
            <div style="display: inline-block; background: #081427; border-left: 3px solid #00f5b8; border-top: 1px solid #142f57; border-right: 1px solid #142f57; border-bottom: 1px solid #142f57; border-radius: 8px; padding: 12px 16px; max-width: 88%;">
                <div style="font-size: 10px; font-weight: 800; color: #00f5b8; margin-bottom: 6px; letter-spacing: 1px; font-family: 'Consolas', monospace;">⚡ TURTLE // {now}</div>
                <div style="color: #e2f0fc; font-size: 13px; line-height: 1.5;">{formatted}</div>
            </div>
        </div>
        """
        self.chat.append(html)

    def append_system_pill(self, text):
        html = f"""
        <div style="margin: 4px 0; text-align: center;">
            <span style="background: rgba(0, 245, 184, 0.08); border: 1px solid rgba(0, 245, 184, 0.25); border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: 700; color: #00f5b8; font-family: 'Consolas', monospace;">
                {text}
            </span>
        </div>
        """
        self.chat.append(html)

    def send_text(self):
        text = self.input.text().strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        if not self.agent:
            QMessageBox.warning(self, "System Offline", "GROQ_API_KEY is missing in .env. Please configure and restart.")
            return

        self.input.clear()
        self.append_user_message(text)
        self.set_hud_status("PROCESSING INSTRUCTION...", "PROCESSING")
        is_autonomous = self.autonomous_check.isChecked()

        self.worker = TaskWorker(self.agent, text, autonomous=is_autonomous, parent=self)
        self.worker.finished_text.connect(self.on_answer)
        self.worker.status.connect(self.on_worker_status)
        self.worker.approval_requested.connect(self.ask_approval)
        self.set_busy(True)
        self.worker.start()

    def on_worker_status(self, status_msg):
        self.set_hud_status(status_msg, "PROCESSING")
        self.append_system_pill(status_msg)

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
        self.append_turtle_message(answer)
        self.set_hud_status("SYSTEMS NOMINAL // READY", "IDLE")
        self.set_busy(False)
        self.start_speech(answer)

    def start_speech(self, text):
        if not self.speak_check.isChecked() or not text:
            return
        self.stop_speaking()
        self.speak_worker = SpeakWorker(text)
        self.speak_worker.speech_started.connect(self.on_speech_started)
        self.speak_worker.speech_finished.connect(self.on_speech_finished)
        self.speak_worker.start()

    def stop_speaking(self):
        stop_speech()
        if self.speak_worker:
            self.speak_worker.stop()
        self.on_speech_finished()
        self.set_hud_status("VOICE OUTPUT SILENCED", "IDLE")

    def on_speech_started(self):
        self.set_hud_status("VOCALIZING RESPONSE", "SPEAKING")
        self.stop_speech_button.setEnabled(True)
        self.stop_speech_button.setText("⏹ Silence Voice (Esc)")

    def on_speech_finished(self):
        self.stop_speech_button.setEnabled(False)
        self.stop_speech_button.setText("⏹ Silence Voice")
        if not (self.worker and self.worker.isRunning()):
            self.set_hud_status("SYSTEMS NOMINAL // READY", "IDLE")

    def analyze_screen(self):
        if (self.worker and self.worker.isRunning()) or (self.vision_worker and self.vision_worker.isRunning()):
            return

        self.set_hud_status("CAPTURING DESKTOP TELEMETRY...", "PROCESSING")
        self.append_system_pill("OPTICAL SENSORS ACTIVE // ANALYZING SCREEN")
        self.vision_button.setEnabled(False)
        self.vision_worker = VisionWorker("Describe the visible screen and identify key windows, contents, and errors.")
        self.vision_worker.finished_text.connect(self.on_vision_answer)
        self.vision_worker.start()

    def on_vision_answer(self, answer):
        self.append_turtle_message(f"<b>[Visual Inspection Report]</b><br>{answer}")
        self.set_hud_status("SYSTEMS NOMINAL // READY", "IDLE")
        self.vision_button.setEnabled(True)
        self.start_speech(answer)

    def start_voice(self):
        if self.voice_input_worker and self.voice_input_worker.isRunning():
            return
        self.set_hud_status("AUDIO SENSORS LISTENING (5s)...", "LISTENING")
        self.voice_button.setEnabled(False)
        self.voice_input_worker = VoiceWorker()
        self.voice_input_worker.transcript.connect(self.on_transcript)
        self.voice_input_worker.error.connect(self.on_voice_error)
        self.voice_input_worker.start()

    def on_transcript(self, text):
        self.voice_button.setEnabled(True)
        self.set_hud_status("AUDIO CAPTURED // TRANSCRIBED", "IDLE")
        if text:
            self.input.setText(text)
            self.send_text()
        else:
            self.append_turtle_message("I didn't catch that clearly. Please try again.")

    def on_voice_error(self, error):
        self.voice_button.setEnabled(True)
        self.set_hud_status("AUDIO SENSOR FAULT", "IDLE")
        self.append_system_pill(f"VOICE ERROR: {error}")

    def set_busy(self, busy):
        self.send_button.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.voice_button.setEnabled(not busy)
        self.vision_button.setEnabled(not busy)

    def toggle_gesture_control(self):
        from .gesture import get_gesture_controller
        controller = get_gesture_controller()
        if not controller.running:
            controller.show_hud = True
            msg = controller.start()
            self.gesture_button.setText("🛑 Stop Gesture Control")
            self.gesture_button.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #990024, stop:1 #cc0033);
                border: 1px solid #ff3366;
                color: #ffffff;
            """)
            self.set_hud_status("GESTURE TRACKING ACTIVE", "GESTURE")
            self.append_turtle_message(msg)
            self.start_speech("Hand gesture tracking online.")
        else:
            msg = controller.stop()
            self.gesture_button.setText("🖐 Gesture Control")
            self.gesture_button.setStyleSheet("")
            self.set_hud_status("GESTURE TRACKING OFFLINE", "IDLE")
            self.append_turtle_message(msg)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.stop_speaking()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self.stop_speaking()
            from .gesture import get_gesture_controller
            get_gesture_controller().stop()
        except Exception:
            pass
        event.accept()
