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
            amp = True
            batch_size = -1
            try:
                if torch.cuda.is_available():
                    self._broadcast(f"   [Hardware] Using GPU (ROCm/CUDA): {torch.cuda.get_device_name(0)}")
                    device = "cuda"
                    
                    # WORKAROUND for AMD ROCm 6.4.4 Preview on Windows:
                    # Disable cuDNN (which disables MIOpen on ROCm) to prevent the "no such column: mode" MIOpen SQLite crash
                    torch.backends.cudnn.enabled = False
                    self._broadcast(f"   [Hardware] MIOpen bypassed for stability")
                else:
                    import torch_directml
                    # We detect DirectML, but force CPU for training due to unsupported YOLOv8 ops
                    self._broadcast(f"   [Hardware] Using AMD DirectML Device (Forced CPU for Training)")
                    device = "cpu"
                    amp = False
                    batch_size = 16
            except ImportError:
                device = "cpu"
                self._broadcast(f"   [Hardware] Using CPU (No ROCm/DirectML found)")
                amp = False
                batch_size = 16

            # Create a proper 80/20 train/val split for YOLOv8
            import shutil
            import random
            dataset_root = Path(data_path)
            val_path = dataset_root / "val"
            train_path = dataset_root / "train"
            
            if train_path.exists():
                self._broadcast("   [Setup] Creating 80/20 train/val dataset split...")
                val_path.mkdir(parents=True, exist_ok=True)
                
                for cls_dir in train_path.iterdir():
                    if not cls_dir.is_dir():
                        continue
                        
                    class_name = cls_dir.name
                    val_cls_dir = val_path / class_name
                    val_cls_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 1. Move everything from val back to train first (for re-training)
                    for f in val_cls_dir.iterdir():
                        shutil.move(str(f), str(cls_dir / f.name))
                        
                    # 2. Get all images in train
                    all_images = [f for f in cls_dir.iterdir() if f.is_file()]
                    total_imgs = len(all_images)
                    
                    if total_imgs > 0:
                        # 3. Calculate 20% for val
                        val_count = max(1, int(total_imgs * 0.2)) if total_imgs >= 2 else 0
                        train_count = total_imgs - val_count
                        
                        # 4. Randomly select and move to val
                        val_images = random.sample(all_images, val_count)
                        for img in val_images:
                            shutil.move(str(img), str(val_cls_dir / img.name))
                            
                        self._broadcast(f"   [{class_name}] Total: {total_imgs} images -> Train: {train_count} | Val: {val_count}")

            # Run training
            model = YOLO("yolov8n-cls.pt")
            results = model.train(
                data=data_path,
                epochs=50,
                imgsz=224,
                batch=batch_size,
                patience=10,    # Early stopping
                device=device,  # Use detected device
                amp=amp,        # Disable AMP for DirectML/CPU
                project=project_path,
                name="train",
                exist_ok=True,  # Overwrite previous run
                verbose=True,
            )

            # Find best.pt or last.pt
            weights_dir = Path(project_path) / "train" / "weights"
            best_pt = weights_dir / "best.pt"
            last_pt = weights_dir / "last.pt"

            if best_pt.exists():
                self._model_path = str(best_pt)
                self._state = "completed"
                self._broadcast("=" * 60)
                self._broadcast(f"✅ Training Complete! Model saved to: {best_pt}")
                self._broadcast("=" * 60)
            elif last_pt.exists():
                self._model_path = str(last_pt)
                self._state = "completed"
                self._broadcast("=" * 60)
                self._broadcast(f"✅ Training Complete! Model saved to: {last_pt}")
                self._broadcast("=" * 60)
            else:
                # Fallback: search for best.pt or last.pt in runs directory
                for root, dirs, files in os.walk(project_path):
                    if "best.pt" in files:
                        self._model_path = os.path.join(root, "best.pt")
                        break
                    elif "last.pt" in files:
                        self._model_path = os.path.join(root, "last.pt")

                if self._model_path:
                    self._state = "completed"
                    self._broadcast(f"✅ Training Complete! Model: {self._model_path}")
                else:
                    self._state = "failed"
                    self._error = "Training finished but no model weights found"
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
