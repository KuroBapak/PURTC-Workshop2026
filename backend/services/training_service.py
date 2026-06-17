"""
Training Service — Orchestrates YOLOv8 classification training with stdout capture.
Runs training in a background thread to avoid blocking the FastAPI event loop.
"""

import io
import os
import sys
import threading
from typing import Callable, Optional
from pathlib import Path


class StreamCapture(io.TextIOBase):
    """Custom stream that captures stdout and forwards to a callback."""

    def __init__(self, callback: Callable[[str], None], original_stdout):
        super().__init__()
        self._callback = callback
        self._original = original_stdout
        self._buffer = ""

    def write(self, text: str) -> int:
        # Write to original stdout as well
        if self._original:
            self._original.write(text)
            self._original.flush()

        # Buffer and emit complete lines
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            stripped = line.strip()
            if stripped:
                self._callback(stripped)
        return len(text)

    def flush(self):
        if self._original:
            self._original.flush()
        # Emit any remaining buffer
        if self._buffer.strip():
            self._callback(self._buffer.strip())
            self._buffer = ""


class TrainingService:
    """Manages YOLOv8 classification model training."""

    def __init__(self):
        self._state: str = "idle"  # idle, running, completed, failed
        self._thread: Optional[threading.Thread] = None
        self._model_path: Optional[str] = None
        self._error: Optional[str] = None
        self._listeners: list[Callable[[str], None]] = []
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def model_path(self) -> Optional[str]:
        return self._model_path

    @property
    def error(self) -> Optional[str]:
        return self._error

    def add_listener(self, callback: Callable[[str], None]):
        """Register a callback to receive training log lines."""
        with self._lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], None]):
        """Unregister a log callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _broadcast(self, line: str):
        """Send a log line to all registered listeners."""
        with self._lock:
            for listener in self._listeners:
                try:
                    listener(line)
                except Exception:
                    pass

    def start_training(self, data_path: str, project_path: str) -> bool:
        """
        Start YOLOv8 classification training in a background thread.
        Returns True if training was started, False if already running.
        """
        if self._state == "running":
            return False

        self._state = "running"
        self._model_path = None
        self._error = None

        self._thread = threading.Thread(
            target=self._train_worker,
            args=(data_path, project_path),
            daemon=True
        )
        self._thread.start()
        return True

    def _train_worker(self, data_path: str, project_path: str):
        """Background training worker thread."""
        original_stdout = sys.stdout
        try:
            # Import here to avoid loading YOLO until needed
            from ultralytics import YOLO

            # Set up stdout capture
            capture = StreamCapture(self._broadcast, original_stdout)
            sys.stdout = capture

            self._broadcast("=" * 60)
            self._broadcast("🚀 Starting YOLOv8 Classification Training...")
            self._broadcast(f"   Dataset: {data_path}")
            self._broadcast(f"   Model: yolov8n-cls.pt")
            self._broadcast(f"   Epochs: 50 | ImgSize: 224 | Batch: AutoBatch")
            self._broadcast(f"   Patience: 10 (Early Stopping)")
            self._broadcast("=" * 60)

            # Detect hardware
            import torch
            try:
                if torch.cuda.is_available():
                    self._broadcast(f"   [Hardware] Using GPU (ROCm/CUDA): {torch.cuda.get_device_name(0)}")
                    device = "cuda"
                else:
                    import torch_directml
                    device = torch_directml.device()
                    self._broadcast(f"   [Hardware] Using AMD DirectML Device")
            except ImportError:
                device = "cpu"
                self._broadcast(f"   [Hardware] Using CPU (No ROCm/DirectML found)")

            # Run training
            model = YOLO("yolov8n-cls.pt")
            results = model.train(
                data=data_path,
                epochs=50,
                imgsz=224,
                batch=-1,       # AutoBatch — auto-detect optimal batch size per GPU
                patience=10,    # Early stopping
                device=device,  # Use detected device
                project=project_path,
                name="train",
                exist_ok=True,  # Overwrite previous run
                verbose=True,
            )

            # Find best.pt
            weights_dir = Path(project_path) / "train" / "weights"
            best_pt = weights_dir / "best.pt"

            if best_pt.exists():
                self._model_path = str(best_pt)
                self._state = "completed"
                self._broadcast("=" * 60)
                self._broadcast(f"✅ Training Complete! Model saved to: {best_pt}")
                self._broadcast("=" * 60)
            else:
                # Fallback: search for best.pt in runs directory
                for root, dirs, files in os.walk(project_path):
                    if "best.pt" in files:
                        self._model_path = os.path.join(root, "best.pt")
                        break

                if self._model_path:
                    self._state = "completed"
                    self._broadcast(f"✅ Training Complete! Model: {self._model_path}")
                else:
                    self._state = "failed"
                    self._error = "Training finished but best.pt not found"
                    self._broadcast(f"❌ Error: {self._error}")

        except Exception as e:
            self._state = "failed"
            self._error = str(e)
            self._broadcast(f"❌ Training Failed: {e}")
        finally:
            sys.stdout = original_stdout
            # Flush remaining buffer
            capture.flush()


# Module-level singleton instance
training_service = TrainingService()
