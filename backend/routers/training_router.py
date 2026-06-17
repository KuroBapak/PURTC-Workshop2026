"""
Training Router — Triggers YOLOv8 training and streams logs via WebSocket.
"""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from services.training_service import training_service


router = APIRouter()
ws_router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset" / "train"
RUNS_DIR = PROJECT_ROOT / "runs" / "classify"


@router.post("/start")
async def start_training():
    """Start YOLOv8 classification training."""
    # Validate dataset
    if not DATASET_DIR.exists():
        raise HTTPException(status_code=400, detail="Dataset directory not found")

    classes = [d for d in DATASET_DIR.iterdir() if d.is_dir()]
    if len(classes) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 2 classes for training. Found: {len(classes)}"
        )

    # Check each class has images
    for cls_dir in classes:
        images = [f for f in cls_dir.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
        if len(images) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Class '{cls_dir.name}' has no images"
            )

    # Check if already running
    if training_service.state == "running":
        raise HTTPException(status_code=409, detail="Training is already running")

    # Start training
    data_path = str(PROJECT_ROOT / "dataset")
    project_path = str(RUNS_DIR)

    success = training_service.start_training(data_path, project_path)
    if not success:
        raise HTTPException(status_code=409, detail="Training could not be started")

    return {"status": "started"}


@router.get("/status")
async def get_training_status():
    """Get current training status."""
    result = {
        "state": training_service.state,
    }
    if training_service.model_path:
        result["model_path"] = training_service.model_path
    if training_service.error:
        result["error"] = training_service.error
    return result


@ws_router.websocket("/ws/training/logs")
async def training_logs_websocket(websocket: WebSocket):
    """
    WebSocket that streams training log lines in real-time.
    Sends structured JSON on completion/failure.
    """
    await websocket.accept()
    print("[Training WS] Client connected")

    # Queue for this client's messages
    message_queue: asyncio.Queue = asyncio.Queue()

    def on_log_line(line: str):
        """Callback from TrainingService — puts line into async queue."""
        try:
            message_queue.put_nowait(line)
        except asyncio.QueueFull:
            pass

    # Register listener
    training_service.add_listener(on_log_line)

    try:
        # Send current state if training already completed/failed
        if training_service.state == "completed":
            await websocket.send_json({
                "status": "completed",
                "model_path": training_service.model_path
            })
            return
        elif training_service.state == "failed":
            await websocket.send_json({
                "status": "failed",
                "error": training_service.error
            })
            return

        # Stream logs
        while True:
            try:
                # Wait for a log line with timeout
                line = await asyncio.wait_for(message_queue.get(), timeout=1.0)
                await websocket.send_text(line)

                # Check if training finished
                if training_service.state == "completed":
                    await websocket.send_json({
                        "status": "completed",
                        "model_path": training_service.model_path
                    })
                    break
                elif training_service.state == "failed":
                    await websocket.send_json({
                        "status": "failed",
                        "error": training_service.error
                    })
                    break

            except asyncio.TimeoutError:
                # No new logs — check if training is done
                if training_service.state == "completed":
                    await websocket.send_json({
                        "status": "completed",
                        "model_path": training_service.model_path
                    })
                    break
                elif training_service.state == "failed":
                    await websocket.send_json({
                        "status": "failed",
                        "error": training_service.error
                    })
                    break
                # If idle and no training running, keep waiting
                continue

    except WebSocketDisconnect:
        print("[Training WS] Client disconnected")
    except Exception as e:
        print(f"[Training WS] Error: {e}")
    finally:
        training_service.remove_listener(on_log_line)
