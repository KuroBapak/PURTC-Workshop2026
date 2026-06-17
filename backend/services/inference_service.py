"""
Inference Service — YOLOv8 classification + Haar Cascade face detection.
Generates MJPEG frames with bounding box overlays and classification labels.
"""

import threading
import time
from typing import Optional, Generator
import cv2
import numpy as np

from .camera_manager import camera_manager
from .serial_manager import serial_manager


class InferenceService:
    """Manages live inference with face detection overlay and MJPEG streaming."""

    def __init__(self):
        self._model = None
        self._face_cascade = None
        self._threshold: float = 0.70  # Default 70%
        self._running: bool = False
        self._latest_result: Optional[dict] = None
        self._lock = threading.Lock()
        self._class_names: list[str] = []

    def start(self, model_path: str, threshold: float = 0.70, camera_index: int = 0) -> bool:
        """Load models and start the inference engine."""
        try:
            from ultralytics import YOLO

            # Detect hardware and load YOLOv8 classification model
            self._model = YOLO(model_path)
            
            import torch
            try:
                if torch.cuda.is_available():
                    print(f"[InferenceService] Using GPU (ROCm/CUDA): {torch.cuda.get_device_name(0)}")
                    self._model.to("cuda")
                else:
                    import torch_directml
                    print("[InferenceService] Using AMD DirectML Device")
                    self._model.to(torch_directml.device())
            except ImportError:
                print("[InferenceService] Using CPU (No ROCm/DirectML found)")
                self._model.to("cpu")
                
            print(f"[InferenceService] Loaded model: {model_path}")

            # Get class names from the model
            if hasattr(self._model, 'names'):
                self._class_names = list(self._model.names.values())
                print(f"[InferenceService] Classes: {self._class_names}")

            # Load Haar Cascade for face detection (built into OpenCV)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
            if self._face_cascade.empty():
                print("[InferenceService] Warning: Haar Cascade failed to load")

            # Open camera
            if not camera_manager.open(camera_index=camera_index):
                print(f"[InferenceService] Failed to open camera {camera_index}")
                return False

            self._threshold = threshold
            self._running = True
            print(f"[InferenceService] Started with threshold: {threshold}")
            return True

        except Exception as e:
            print(f"[InferenceService] Start error: {e}")
            return False

    def stop(self):
        """Stop inference and release resources."""
        self._running = False
        camera_manager.close()
        self._model = None
        self._face_cascade = None
        self._latest_result = None
        print("[InferenceService] Stopped")

    def set_threshold(self, value: float):
        """Update confidence threshold (thread-safe)."""
        with self._lock:
            self._threshold = max(0.0, min(1.0, value))
            print(f"[InferenceService] Threshold updated: {self._threshold}")

    def get_latest_result(self) -> Optional[dict]:
        """Get the latest inference result."""
        with self._lock:
            return self._latest_result

    def generate_frames(self) -> Generator[bytes, None, None]:
        """
        Generator that yields MJPEG frames with face detection boxes
        and classification overlays.
        """
        consecutive_granted_frames = 0
        frames_required_for_unlock = 20  # ~1 to 1.5 seconds at 15-20 FPS
        unlock_hold_frames = 0           # Keep door open after lookaway

        while self._running:
            frame = camera_manager.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            faces_detected = 0
            best_class_name = "No Face"
            best_confidence = 0.0
            frame_status = "denied"
            face_results = []

            # --- Step 1: Face Detection (Haar Cascade) ---
            faces = []
            if self._face_cascade is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                )
                faces_detected = len(faces) if isinstance(faces, np.ndarray) else 0

            with self._lock:
                threshold = self._threshold

            # --- Step 2: Classification (YOLOv8-cls on EACH face independently) ---
            if self._model is not None and faces_detected > 0:
                for (x, y, w, h) in faces:
                    margin_x = int(w * 0.1)
                    margin_y = int(h * 0.1)
                    x1 = max(0, x - margin_x)
                    y1 = max(0, y - margin_y)
                    x2 = min(frame.shape[1], x + w + margin_x)
                    y2 = min(frame.shape[0], y + h + margin_y)
                    
                    face_crop = frame[y1:y2, x1:x2]
                    
                    f_class = "unknown"
                    f_conf = 0.0
                    f_status = "denied"

                    try:
                        results = self._model.predict(face_crop, verbose=False, imgsz=224)
                        if results and len(results) > 0:
                            result = results[0]
                            if hasattr(result, 'probs') and result.probs is not None:
                                top1_idx = result.probs.top1
                                f_conf = float(result.probs.top1conf)
                                f_class = result.names[top1_idx]
                    except Exception as e:
                        pass

                    if f_conf > threshold and f_class not in ["unknown", "No Face"]:
                        f_status = "granted"
                        frame_status = "granted"

                    face_results.append({
                        "box": (x, y, w, h),
                        "class": f_class,
                        "conf": f_conf,
                        "status": f_status
                    })

                    # Track best result for the UI
                    if f_status == "granted" and f_conf > best_confidence:
                        best_class_name = f_class
                        best_confidence = f_conf
                    elif frame_status == "denied" and f_conf > best_confidence:
                        best_class_name = f_class
                        best_confidence = f_conf

            # --- Step 3: Hardware & Verification Logic ---
            hardware_state = "locked"
            progress = 0.0

            if frame_status == "granted":
                if consecutive_granted_frames < frames_required_for_unlock:
                    consecutive_granted_frames += 1
                    hardware_state = "verifying"
                    progress = consecutive_granted_frames / frames_required_for_unlock
                else:
                    hardware_state = "unlocked"
                    progress = 1.0
                    unlock_hold_frames = 40  # Hold unlock for ~2.5 seconds if they look away
                    serial_manager.send("OPEN")
            else:
                if unlock_hold_frames > 0:
                    unlock_hold_frames -= 1
                    hardware_state = "unlocked"
                    progress = 1.0
                    serial_manager.send("OPEN")
                else:
                    consecutive_granted_frames = max(0, consecutive_granted_frames - 2) # Drain progress if look away
                    hardware_state = "locked" if consecutive_granted_frames == 0 else "verifying"
                    progress = consecutive_granted_frames / frames_required_for_unlock
                    serial_manager.send("CLOSE")

            # --- Step 4: Draw bounding boxes and labels ---
            if faces_detected > 0:
                for res in face_results:
                    x, y, w, h = res["box"]
                    color = (0, 255, 136) if res["status"] == "granted" else (51, 51, 255)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

                    label = f"{res['class']} {res['conf']:.0%}"
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    label_y = max(y - 10, label_size[1] + 10)

                    cv2.rectangle(frame, (x, label_y - label_size[1] - 5), (x + label_size[0] + 5, label_y + 5), color, -1)
                    cv2.putText(frame, label, (x + 2, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                cv2.putText(frame, "No Face 0%", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (51, 51, 255), 2)

            # --- Step 5: Status bar at bottom ---
            h, w = frame.shape[:2]
            
            # Dynamic status text based on hardware state
            if hardware_state == "unlocked":
                status_text = "ACCESS GRANTED - UNLOCKED"
                bar_color = (0, 255, 136)
            elif hardware_state == "verifying":
                status_text = f"VERIFYING... HOLD STILL [{int(progress*100)}%]"
                bar_color = (0, 165, 255)  # Orange
            else:
                status_text = "LOCKED"
                bar_color = (51, 51, 255)
                
            cv2.rectangle(frame, (0, h - 35), (int(w * (progress if hardware_state == 'verifying' else 1.0)), h), bar_color, -1)
            cv2.putText(frame, status_text, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # --- Step 6: Store result for WebSocket ---
            with self._lock:
                self._latest_result = {
                    "class_name": best_class_name,
                    "confidence": round(best_confidence, 4),
                    "status": "granted" if hardware_state == "unlocked" else "denied",
                    "faces_detected": faces_detected,
                    "hardware_state": hardware_state,
                    "progress": progress
                }

            # --- Step 7: Encode frame as JPEG and yield for MJPEG ---
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

            time.sleep(0.05)

    @property
    def is_running(self) -> bool:
        return self._running


# Module-level singleton instance
inference_service = InferenceService()
