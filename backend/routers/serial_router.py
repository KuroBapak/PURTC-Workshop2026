"""
Serial Router — COM port scanning, connect/disconnect, and status endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.serial_manager import serial_manager


router = APIRouter()


class ConnectRequest(BaseModel):
    port: str


@router.get("/ports")
async def scan_ports():
    """Scan and return available COM ports."""
    ports = serial_manager.scan_ports()
    return {"ports": ports}


@router.post("/connect")
async def connect_port(request: ConnectRequest):
    """Connect to a specified COM port."""
    success = serial_manager.connect(request.port)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to connect to {request.port}")
    return {"status": "connected", "port": request.port}


@router.post("/disconnect")
async def disconnect_port():
    """Disconnect the active serial connection."""
    serial_manager.disconnect()
    return {"status": "disconnected"}


@router.get("/status")
async def get_status():
    """Get current serial connection status (for ESP32 badge heartbeat)."""
    return {"status": serial_manager.get_status()}


@router.post("/skip")
async def skip_hardware():
    """Mark as software-only mode (no ESP32 hardware)."""
    serial_manager.set_skipped()
    return {"status": "skipped"}
