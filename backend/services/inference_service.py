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

    def start(self, model_path: str, threshold: float = 0.70) -> bool:
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
            if not camera_manager.open():
                print("[InferenceService] Failed to open camera")
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
        while self._running:
            frame = camera_manager.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            faces_detected = 0
            class_name = "unknown"
            confidence = 0.0
            status = "denied"

            # --- Step 1: Face Detection (Haar Cascade) ---
            if self._face_cascade is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(60, 60),
                )
                faces_detected = len(faces) if isinstance(faces, np.ndarray) else 0

            # --- Step 2: Classification (YOLOv8-cls on full frame) ---
            if self._model is not None:
                try:
                    results = self._model.predict(
                        frame,
                        verbose=False,
                        imgsz=224,
                    )
                    if results and len(results) > 0:
                        result = results[0]
                        if hasattr(result, 'probs') and result.probs is not None:
                            top1_idx = result.probs.top1
                            top1_conf = float(result.probs.top1conf)
                            class_name = result.names[top1_idx]
                            confidence = top1_conf
                except Exception as e:
                    print(f"[InferenceService] Predict error: {e}")

            # --- Step 3: Determine access status ---
            with self._lock:
                threshold = self._threshold

            if confidence > threshold and class_name != "unknown":
                status = "granted"
            else:
                status = "denied"

            # --- Step 4: Draw bounding boxes and labels ---
            if faces_detected > 0:
                for (x, y, w, h) in faces:
                    # Choose color based on status
                    color = (0, 255, 136) if status == "granted" else (51, 51, 255)  # Green or Red (BGR)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

                    # Draw label above bounding box
                    label = f"{class_name} {confidence:.0%}"
                    label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    label_y = max(y - 10, label_size[1] + 10)

                    # Background rectangle for label
                    cv2.rectangle(
                        frame,
                        (x, label_y - label_size[1] - 5),
                        (x + label_size[0] + 5, label_y + 5),
                        color, -1
                    )
                    cv2.putText(
                        frame, label,
                        (x + 2, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (255, 255, 255), 2
                    )
            else:
                # No face detected — show classification result in top-left
                label = f"{class_name} {confidence:.0%}"
                color = (0, 255, 136) if status == "granted" else (51, 51, 255)
                cv2.putText(
                    frame, label,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    color, 2
                )

            # --- Step 5: Status bar at bottom ---
            h, w = frame.shape[:2]
            status_text = f"{'ACCESS GRANTED' if status == 'granted' else 'ACCESS DENIED'} | Threshold: {threshold:.0%}"
            bar_color = (0, 255, 136) if status == "granted" else (51, 51, 255)
            cv2.rectangle(frame, (0, h - 35), (w, h), bar_color, -1)
            cv2.putText(
                frame, status_text,
                (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 2
            )

            # --- Step 6: Send serial command (with debounce handled by SerialManager) ---
            if status == "granted":
                serial_manager.send("OPEN")
            else:
                serial_manager.send("CLOSE")

            # --- Step 7: Store result for WebSocket ---
            result_dict = {
                "class_name": class_name,
                "confidence": round(confidence, 4),
                "status": status,
                "faces_detected": faces_detected,
            }
            with self._lock:
                self._latest_result = result_dict

            # --- Step 8: Encode frame as JPEG and yield for MJPEG ---
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_bytes = buffer.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                frame_bytes +
                b"\r\n"
            )

            # Small delay to control frame rate (~20 FPS)
            time.sleep(0.05)

    @property
    def is_running(self) -> bool:
        return self._running


# Module-level singleton instance
inference_service = InferenceService()
