import ctypes
import math
import os
import threading
import time
import urllib.request
from pathlib import Path
import sys

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Windows User32 API Constants for zero-latency mouse control
user32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

def get_model_path():
    """Resolve path to hand_landmarker.task whether running from source or frozen .exe."""
    if getattr(sys, 'frozen', False):
        meipass = Path(getattr(sys, '_MEIPASS', ''))
        for candidate in [
            meipass / "meck_ai" / "models" / "hand_landmarker.task",
            meipass / "models" / "hand_landmarker.task",
            Path(sys.executable).parent / "models" / "hand_landmarker.task",
        ]:
            if candidate.exists():
                return candidate
    return Path(__file__).resolve().parent / "models" / "hand_landmarker.task"

MODEL_PATH = get_model_path()
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

def ensure_model_exists():
    """Download the official hand landmarker model if not present."""
    path = get_model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        urllib.request.urlretrieve(MODEL_URL, path)
    return path

def distance_2d(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

class HandGestureController:
    """Autonomous Hand Gesture Controller for Windows Desktop.
    
    Gestures:
    - Hand as cursor: Move index fingertip to move mouse smoothly.
    - Index + Thumb pinch: Left Click & Drag (holding keeps left mouse button down).
    - Pinky + Thumb pinch: Right Click.
    - All finger hold (fist/closed hand): Scroll (move hand up to scroll up, down to scroll down).
    """

    def __init__(self, camera_index=0, show_hud=True):
        self.camera_index = camera_index
        self.show_hud = show_hud
        self.running = False
        self.thread = None
        self.error_message = None

        # Screen dimensions
        self.screen_w = user32.GetSystemMetrics(0)
        self.screen_h = user32.GetSystemMetrics(1)

        # Mouse state
        self.prev_x = self.screen_w / 2
        self.prev_y = self.screen_h / 2
        self.is_left_down = False
        self.last_right_click_time = 0
        self.is_holding = False
        self.scroll_anchor_y = None

        # Movement smoothing
        self.smooth_factor = 0.40
        self.margin_x = 0.16
        self.margin_y = 0.16

        self.last_gesture_text = "Idle"

    def start(self):
        if self.running:
            return "Gesture control is already active, Sir."
        
        self.error_message = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        # Give thread a moment to verify camera initialization
        time.sleep(0.3)
        if self.error_message:
            self.running = False
            return self.error_message

        return "Hand gesture control activated. Index-thumb to left-click, pinky-thumb to right-click, and hold all fingers to scroll."

    def stop(self):
        if not self.running:
            return "Gesture control is not active, Sir."
        self.running = False
        if self.is_left_down:
            try:
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            except Exception:
                pass
            self.is_left_down = False
        if self.thread:
            self.thread.join(timeout=1.5)
            self.thread = None
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        return "Hand gesture control deactivated, Sir."

    def _run(self):
        try:
            actual_model_path = ensure_model_exists()
            base_options = python.BaseOptions(model_asset_path=str(actual_model_path))
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.6,
            )
            detector = vision.HandLandmarker.create_from_options(options)
        except Exception as e:
            self.error_message = f"Failed to initialize MediaPipe Hand Landmarker: {e}"
            self.running = False
            return

        # Attempt opening camera with DirectShow on Windows first for fast open
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        
        if not cap.isOpened():
            self.error_message = "Camera could not be accessed. Please ensure webcam is connected and not used by another application."
            self.running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        prev_time = time.time()

        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            try:
                detection_result = detector.detect(mp_image)
            except Exception:
                detection_result = None

            gesture_name = "SEARCHING HAND"
            gesture_color = (120, 120, 120)

            if detection_result and detection_result.hand_landmarks:
                landmarks = detection_result.hand_landmarks[0]

                wrist = landmarks[0]
                thumb_tip = landmarks[4]
                index_mcp = landmarks[5]
                index_pip = landmarks[6]
                index_tip = landmarks[8]
                middle_mcp = landmarks[9]
                middle_pip = landmarks[10]
                middle_tip = landmarks[12]
                ring_pip = landmarks[14]
                ring_tip = landmarks[16]
                pinky_pip = landmarks[18]
                pinky_tip = landmarks[20]

                hand_scale = distance_2d(wrist, middle_mcp)
                if hand_scale < 0.05:
                    hand_scale = 0.05

                # 1. Check Fist / Closed hand (All fingers held)
                d_index_curl = distance_2d(index_tip, middle_mcp)
                d_middle_curl = distance_2d(middle_tip, middle_mcp)
                d_ring_curl = distance_2d(ring_tip, middle_mcp)
                d_pinky_curl = distance_2d(pinky_tip, middle_mcp)

                all_fingers_held = (
                    (d_index_curl / hand_scale < 0.58) and
                    (d_middle_curl / hand_scale < 0.55) and
                    (d_ring_curl / hand_scale < 0.55) and
                    (d_pinky_curl / hand_scale < 0.58)
                )

                d_index_thumb = distance_2d(index_tip, thumb_tip) / hand_scale
                d_pinky_thumb = distance_2d(pinky_tip, thumb_tip) / hand_scale

                now = time.time()

                if all_fingers_held:
                    gesture_name = "HOLD: SCROLLING"
                    gesture_color = (0, 165, 255)

                    if self.is_left_down:
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        self.is_left_down = False

                    hand_y = middle_mcp.y
                    if not self.is_holding or self.scroll_anchor_y is None:
                        self.is_holding = True
                        self.scroll_anchor_y = hand_y
                    else:
                        dy = hand_y - self.scroll_anchor_y
                        threshold = 0.015
                        if abs(dy) > threshold:
                            scroll_speed = int(np.clip(abs(dy) * 450, 60, 360))
                            scroll_direction = 1 if dy < 0 else -1
                            user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, scroll_direction * scroll_speed, 0)
                            self.scroll_anchor_y = hand_y - (threshold if dy > 0 else -threshold)

                else:
                    self.is_holding = False
                    self.scroll_anchor_y = None

                    # Pinky + Thumb pinch = Right Click
                    if d_pinky_thumb < 0.28:
                        gesture_name = "PINCH: RIGHT CLICK"
                        gesture_color = (255, 0, 255)
                        if now - self.last_right_click_time > 0.45:
                            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                            self.last_right_click_time = now

                    # Index + Thumb pinch = Left Click & Drag
                    elif d_index_thumb < 0.28:
                        gesture_name = "PINCH: LEFT CLICK"
                        gesture_color = (0, 255, 255)
                        if not self.is_left_down:
                            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            self.is_left_down = True
                    else:
                        if self.is_left_down and d_index_thumb > 0.35:
                            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            self.is_left_down = False
                        gesture_name = "CURSOR TRACKING"
                        gesture_color = (0, 255, 128)

                    # Cursor mapping
                    raw_x = index_tip.x
                    raw_y = index_tip.y

                    norm_x = (raw_x - self.margin_x) / (1.0 - 2.0 * self.margin_x)
                    norm_y = (raw_y - self.margin_y) / (1.0 - 2.0 * self.margin_y)
                    norm_x = max(0.0, min(1.0, norm_x))
                    norm_y = max(0.0, min(1.0, norm_y))

                    target_x = norm_x * self.screen_w
                    target_y = norm_y * self.screen_h

                    smooth_x = self.prev_x + (target_x - self.prev_x) * self.smooth_factor
                    smooth_y = self.prev_y + (target_y - self.prev_y) * self.smooth_factor

                    user32.SetCursorPos(int(smooth_x), int(smooth_y))
                    self.prev_x = smooth_x
                    self.prev_y = smooth_y

                if self.show_hud:
                    connections = [
                        (0, 1), (1, 2), (2, 3), (3, 4),
                        (0, 5), (5, 6), (6, 7), (7, 8),
                        (5, 9), (9, 10), (10, 11), (11, 12),
                        (9, 13), (13, 14), (14, 15), (15, 16),
                        (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)
                    ]
                    for start_idx, end_idx in connections:
                        p1 = landmarks[start_idx]
                        p2 = landmarks[end_idx]
                        x1, y1 = int(p1.x * w), int(p1.y * h)
                        x2, y2 = int(p2.x * w), int(p2.y * h)
                        cv2.line(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)

                    for idx, color, size in [
                        (4, (0, 255, 255), 7),
                        (8, (0, 255, 0), 9),
                        (12, (255, 200, 0), 6),
                        (16, (255, 200, 0), 6),
                        (20, (255, 0, 255), 7),
                    ]:
                        pt = landmarks[idx]
                        cv2.circle(frame, (int(pt.x * w), int(pt.y * h)), size, color, -1)

            else:
                if self.is_left_down:
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    self.is_left_down = False
                self.is_holding = False

            self.last_gesture_text = gesture_name

            if self.show_hud:
                cv2.rectangle(frame, (0, 0), (w, 55), (25, 18, 10), -1)
                cv2.line(frame, (0, 55), (w, 55), (184, 245, 0), 1)

                curr_time = time.time()
                fps = int(1.0 / (curr_time - prev_time + 1e-6))
                prev_time = curr_time

                cv2.putText(frame, "TURTLE GESTURE CONTROLLER", (14, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (184, 245, 0), 2)
                cv2.putText(frame, f"STATUS: {gesture_name}", (14, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.50, gesture_color, 2)
                cv2.putText(frame, f"{fps} FPS", (w - 75, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 128), 1)

                cv2.rectangle(frame, (0, h - 30), (w, h), (15, 20, 28), -1)
                cv2.putText(
                    frame,
                    "Index+Thumb: Left Click | Pinky+Thumb: Right Click | Fist: Scroll | 'q': Hide HUD",
                    (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38,
                    (200, 220, 240),
                    1
                )

                try:
                    cv2.imshow("TURTLE Hand Gesture HUD", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord('q'), 27):
                        self.show_hud = False
                        cv2.destroyAllWindows()
                except Exception:
                    self.show_hud = False

            time.sleep(0.005)

        cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass


_controller = None

def get_gesture_controller():
    global _controller
    if _controller is None:
        _controller = HandGestureController()
    return _controller

def start_gesture_control():
    controller = get_gesture_controller()
    return controller.start()

def stop_gesture_control():
    controller = get_gesture_controller()
    return controller.stop()
