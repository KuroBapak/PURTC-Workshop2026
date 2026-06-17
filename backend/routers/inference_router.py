"""
Inference Router — MJPEG video stream, threshold config, and WebSocket results.
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.inference_service import inference_service
from services.training_service import training_service


router = APIRouter()
ws_router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class StartInferenceRequest(BaseModel):
    camera_index: int = 0

class ThresholdRequest(BaseModel):
    value: float


def find_best_model() -> str | None:
    """Find the latest best.pt model file."""
    # Check if training service has a path
    if training_service.model_path and os.path.exists(training_service.model_path):
        return training_service.model_path

    # Search in runs directory
    runs_dir = PROJECT_ROOT / "runs" / "classify"
    if runs_dir.exists():
        for root, dirs, files in os.walk(str(runs_dir)):
            if "best.pt" in files:
                return os.path.join(root, "best.pt")

    return None


@router.post("/start")
async def start_inference(request: StartInferenceRequest = StartInferenceRequest()):
    """Start the inference engine and MJPEG stream."""
    if inference_service.is_running:
        raise HTTPException(status_code=409, detail="Inference is already running")

    model_path = find_best_model()
    if not model_path:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Complete training first."
        )

    success = inference_service.start(model_path, camera_index=request.camera_index)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start inference engine")

    return {"status": "started", "model_path": model_path}


@router.post("/stop")
async def stop_inference():
    """Stop the inference engine and release camera."""
    inference_service.stop()
    return {"status": "stopped"}


@router.post("/threshold")
async def update_threshold(request: ThresholdRequest):
    """Update the confidence threshold in real-time."""
    value = max(0.0, min(1.0, request.value))
    inference_service.set_threshold(value)
    return {"status": "updated", "threshold": value}


@router.get("/feed")
async def video_feed():
    """MJPEG video stream of annotated inference frames."""
    if not inference_service.is_running:
        raise HTTPException(status_code=400, detail="Inference is not running")

    return StreamingResponse(
        inference_service.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@ws_router.websocket("/ws/inference/results")
async def inference_results_websocket(websocket: WebSocket):
    """
    WebSocket that pushes inference result JSON for each frame.
    Used by the frontend to drive the visual feedback UI (green/red pulse).
    """
    await websocket.accept()
    print("[Inference WS] Client connected")

    last_result = None

    try:
        while True:
            if not inference_service.is_running:
                await asyncio.sleep(0.5)
                continue

            result = inference_service.get_latest_result()
            if result and result != last_result:
                await websocket.send_json(result)
                last_result = result

            await asyncio.sleep(0.1)  # ~10 updates per second

    except WebSocketDisconnect:
        print("[Inference WS] Client disconnected")
    except Exception as e:
        print(f"[Inference WS] Error: {e}")
