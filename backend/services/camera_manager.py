"""
Camera Manager — Singleton service for OpenCV camera access.
Thread-safe wrapper around cv2.VideoCapture for shared camera usage.
"""

import threading
from typing import Optional
import cv2
import numpy as np


class CameraManager:
    """Manages a single camera resource with thread-safe access."""

    _instance: Optional["CameraManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CameraManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cap: Optional[cv2.VideoCapture] = None
        self._camera_lock = threading.Lock()

    def open(self, camera_index: int = 0) -> bool:
        """Open the camera device."""
        with self._camera_lock:
            if self._cap and self._cap.isOpened():
                return True
            self._cap = cv2.VideoCapture(camera_index)
            if not self._cap.isOpened():
                print(f"[CameraManager] Failed to open camera {camera_index}")
                self._cap = None
                return False
            # Set reasonable resolution for workshop
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print(f"[CameraManager] Camera {camera_index} opened")
            return True

    def close(self):
        """Release the camera resource."""
        with self._camera_lock:
            if self._cap and self._cap.isOpened():
                self._cap.release()
                print("[CameraManager] Camera released")
            self._cap = None

    def read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame from the camera (thread-safe)."""
        with self._camera_lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ret, frame = self._cap.read()
            if not ret:
                return None
            return frame

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()


# Module-level singleton instance
camera_manager = CameraManager()
