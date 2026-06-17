"""
Dataset Router — Class CRUD operations and WebSocket burst image capture.
"""

import os
import shutil
from pathlib import Path

import cv2
import numpy as np

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


router = APIRouter()
ws_router = APIRouter()

# Dataset directory (resolved relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset" / "train"

# Load Haar cascade for data collection face cropping
cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(cascade_path)

class CreateClassRequest(BaseModel):
    name: str

@router.get("/classes")
async def list_classes():
    """List all registered classes with image counts."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    classes = []
    for item in sorted(DATASET_DIR.iterdir()):
        if item.is_dir():
            image_count = len([
                f for f in item.iterdir()
                if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png')
            ])
            classes.append({"name": item.name, "count": image_count})
    return {"classes": classes}


@router.post("/classes")
async def create_class(request: CreateClassRequest):
    """Create a new class (creates folder on disk)."""
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Class name cannot be empty")

    class_dir = DATASET_DIR / name
    if class_dir.exists():
        raise HTTPException(status_code=409, detail=f"Class '{name}' already exists")

    class_dir.mkdir(parents=True, exist_ok=True)
    return {"status": "created", "name": name, "path": str(class_dir)}


@router.delete("/classes/{name}")
async def delete_class(name: str):
    """Delete a class and all its images from disk."""
    class_dir = DATASET_DIR / name
    if not class_dir.exists():
        raise HTTPException(status_code=404, detail=f"Class '{name}' not found")

    shutil.rmtree(str(class_dir))
    return {"status": "deleted", "name": name}


@ws_router.websocket("/ws/capture/{class_name}")
async def capture_websocket(websocket: WebSocket, class_name: str):
    """
    WebSocket for burst image capture.
    Receives binary JPEG frames, extracts the face using Haar Cascades,
    and saves the tightly cropped face to the class folder.
    Sends back JSON count updates after each save.
    """
    class_dir = DATASET_DIR / class_name
    if not class_dir.exists():
        await websocket.close(code=4004, reason=f"Class '{class_name}' not found")
        return

    await websocket.accept()
    print(f"[Capture WS] Started for class: {class_name}")

    # Determine starting sequence number
    existing = [
        f for f in class_dir.iterdir()
        if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png')
    ]
    seq = len(existing)
    total_saved = 0

    try:
        while True:
            # Receive binary JPEG data from browser
            data = await websocket.receive_bytes()

            # Decode the image to find the face
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is not None and not face_cascade.empty():
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                )

                if len(faces) > 0:
                    # Find largest face
                    largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
                    x, y, w, h = largest_face
                    
                    # Add 10% margin
                    margin_x = int(w * 0.1)
                    margin_y = int(h * 0.1)
                    x1 = max(0, x - margin_x)
                    y1 = max(0, y - margin_y)
                    x2 = min(frame.shape[1], x + w + margin_x)
                    y2 = min(frame.shape[0], y + h + margin_y)
                    
                    face_crop = frame[y1:y2, x1:x2]
                    
                    # Encode to JPEG and save
                    _, buffer = cv2.imencode('.jpg', face_crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    save_data = buffer.tobytes()

                    seq += 1
                    filename = f"{seq:04d}.jpg"
                    filepath = class_dir / filename

                    with open(filepath, "wb") as f:
                        f.write(save_data)

                    total_saved += 1

            # Send count update back to client
            await websocket.send_json({"count": seq, "saved": total_saved})

    except WebSocketDisconnect:
        print(f"[Capture WS] Disconnected. Saved {total_saved} images for '{class_name}'")
    except Exception as e:
        print(f"[Capture WS] Error: {e}")
    finally:
        try:
            await websocket.send_json({"total": seq, "saved": total_saved, "status": "done"})
        except Exception:
            pass
