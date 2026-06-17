"""
Edge AI Smart Lock — FastAPI Backend
Main application entry point with CORS, router mounting, and startup/shutdown lifecycle.
"""

import os
# Disable MIOpen SQLite caching to prevent "no such column: mode" crashes on Windows ROCm preview
os.environ["MIOPEN_DISABLE_CACHE"] = "1"
os.environ["MIOPEN_DEBUG_DISABLE_FIND_DB"] = "1"

import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routers import serial_router, dataset_router, training_router, inference_router


# Resolve project root (one level above /backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset" / "train"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    # Startup: ensure dataset directory exists
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Startup] Dataset directory: {DATASET_DIR}")
    print(f"[Startup] Project root: {PROJECT_ROOT}")
    
    print("=" * 50)
    print("  Edge AI Smart Lock — Backend Ready!")
    print("  API Docs: http://localhost:8000/docs")
    print("=" * 50)
    yield
    # Shutdown: clean up resources
    from services.serial_manager import serial_manager
    from services.camera_manager import camera_manager
    from services.inference_service import inference_service

    inference_service.stop()
    serial_manager.disconnect()
    camera_manager.close()
    print("[Shutdown] All resources released.")


app = FastAPI(
    title="Edge AI Smart Lock API",
    description="Workshop Edition — Face Recognition Smart Lock Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for workshop convenience (HTML files opened directly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(serial_router.router, prefix="/api/serial", tags=["Serial"])
app.include_router(dataset_router.router, prefix="/api/dataset", tags=["Dataset"])
app.include_router(training_router.router, prefix="/api/training", tags=["Training"])
app.include_router(inference_router.router, prefix="/api/inference", tags=["Inference"])

# Mount WebSocket routes (defined in routers but need the app-level WS path)
app.include_router(dataset_router.ws_router, tags=["Dataset WS"])
app.include_router(training_router.ws_router, tags=["Training WS"])
app.include_router(inference_router.ws_router, tags=["Inference WS"])


@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "running", "project": "Edge AI Smart Lock", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
