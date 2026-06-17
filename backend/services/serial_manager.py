"""
Serial Manager — Singleton service for ESP32 serial communication.
Handles COM port scanning, connection, state-change debounce, and cooldown.
"""

import time
import threading
from typing import Optional
import serial
import serial.tools.list_ports


class SerialManager:
    """Manages serial communication with ESP32 via PySerial."""

    _instance: Optional["SerialManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SerialManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._serial: Optional[serial.Serial] = None
        self._port: Optional[str] = None
        self._skipped: bool = False
        self._last_state: Optional[str] = None  # "OPEN" or "CLOSE"
        self._cooldown_until: float = 0.0
        self._serial_lock = threading.Lock()

    def scan_ports(self) -> list[dict]:
        """Scan and return available COM ports."""
        ports = serial.tools.list_ports.comports()
        return [
            {"port": p.device, "description": p.description}
            for p in sorted(ports, key=lambda x: x.device)
        ]

    def connect(self, port: str, baud: int = 115200) -> bool:
        """Connect to a COM port at specified baud rate."""
        with self._serial_lock:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
                self._serial = serial.Serial(port, baud, timeout=1)
                self._port = port
                self._skipped = False
                self._last_state = None
                self._cooldown_until = 0.0
                return True
            except serial.SerialException as e:
                print(f"[SerialManager] Failed to connect to {port}: {e}")
                self._serial = None
                self._port = None
                return False

    def disconnect(self):
        """Disconnect the active serial connection."""
        with self._serial_lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = None
            self._port = None
            self._last_state = None
            self._cooldown_until = 0.0

    def send(self, payload: str):
        """
        Send a command to ESP32 with state-change debounce.
        Only sends if the state has changed (OPEN→CLOSE or CLOSE→OPEN).
        Enforces a 5-second cooldown after sending "OPEN".
        """
        with self._serial_lock:
            # Software-only mode: no-op
            if self._serial is None or not self._serial.is_open:
                return

            # Debounce: skip if same state
            if payload == self._last_state:
                return

            # Cooldown: skip if within cooldown period after OPEN
            if self._last_state == "OPEN" and time.time() < self._cooldown_until:
                return

            try:
                self._serial.write(f"{payload}\n".encode("utf-8"))
                self._serial.flush()
                self._last_state = payload

                # Set cooldown after OPEN
                if payload == "OPEN":
                    self._cooldown_until = time.time() + 5.0

                print(f"[SerialManager] Sent: {payload}")
            except serial.SerialException as e:
                print(f"[SerialManager] Send error: {e}")

    def get_status(self) -> str:
        """Return current connection status."""
        if self._skipped:
            return "skipped"
        if self._serial and self._serial.is_open:
            return "connected"
        return "disconnected"

    def set_skipped(self):
        """Mark as software-only mode (no hardware)."""
        with self._serial_lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = None
            self._port = None
            self._skipped = True

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open


# Module-level singleton instance
serial_manager = SerialManager()
