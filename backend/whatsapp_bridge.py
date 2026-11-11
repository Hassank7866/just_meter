from __future__ import annotations

import base64
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_DIR = PROJECT_ROOT / "whatsapp-bridge"
BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:5005").rstrip("/")

_bridge_process: subprocess.Popen | None = None
_last_start_attempt: float = 0.0


def is_bridge_reachable() -> bool:
    """Check if WhatsApp bridge server is running and responding."""
    try:
        r = requests.get(f"{BRIDGE_URL}/status", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def is_bridge_process_running() -> bool:
    global _bridge_process
    if _bridge_process is not None and _bridge_process.poll() is None:
        return True
    return False


def ensure_bridge_running() -> None:
    """Ensure the local WhatsApp Web bridge background process is active and singleton."""
    global _bridge_process, _last_start_attempt
    if is_bridge_reachable() or is_bridge_process_running():
        return

    now = time.time()
    if now - _last_start_attempt < 5.0:
        return
    _last_start_attempt = now

    try:
        # Start node server.js in background as a single tracked process
        if sys.platform == "win32":
            _bridge_process = subprocess.Popen(
                ["node", "server.js"],
                cwd=str(BRIDGE_DIR),
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
            )
        else:
            _bridge_process = subprocess.Popen(
                ["node", "server.js"],
                cwd=str(BRIDGE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        print(f"[WhatsApp Bridge] Error starting bridge process: {e}")


def get_bridge_status() -> dict[str, Any]:
    """Retrieve bridge connection state, active user info, and QR code."""
    ensure_bridge_running()
    try:
        r = requests.get(f"{BRIDGE_URL}/status", timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            data["reachable"] = True
            return data
    except Exception as e:
        pass

    return {
        "status": "OFFLINE",
        "connected": False,
        "reachable": False,
        "user": None,
        "qr": None,
        "error": "WhatsApp Bridge server is starting...",
    }


def send_bridge_document(
    to_phone: str,
    pdf_bytes: bytes,
    filename: str = "Official_E_Challan.pdf",
    caption: str | None = None,
) -> dict[str, Any]:
    """Transmit binary PDF document directly to recipient's WhatsApp via local bridge."""
    ensure_bridge_running()
    b64_content = base64.b64encode(pdf_bytes).decode("utf-8")
    payload = {
        "phone": to_phone,
        "filename": filename,
        "base64": b64_content,
        "caption": caption,
    }

    try:
        r = requests.post(f"{BRIDGE_URL}/send-document", json=payload, timeout=30.0)
        if r.status_code == 200:
            return r.json()
        else:
            err_data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return {
                "success": False,
                "error": err_data.get("error") or f"Bridge HTTP {r.status_code}: {r.text}",
            }
    except Exception as e:
        return {"success": False, "error": f"Failed to communicate with WhatsApp Bridge: {e}"}


def send_bridge_text(
    to_phone: str,
    message: str,
) -> dict[str, Any]:
    """Transmit text message directly to recipient's WhatsApp via local bridge."""
    ensure_bridge_running()
    payload = {
        "phone": to_phone,
        "message": message,
    }

    try:
        r = requests.post(f"{BRIDGE_URL}/send-text", json=payload, timeout=20.0)
        if r.status_code == 200:
            return r.json()
        else:
            err_data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return {
                "success": False,
                "error": err_data.get("error") or f"Bridge HTTP {r.status_code}: {r.text}",
            }
    except Exception as e:
        return {"success": False, "error": f"Failed to communicate with WhatsApp Bridge: {e}"}


def request_pairing_code(phone: str) -> dict[str, Any]:
    """Request an 8-digit pairing code to link phone without scanning QR."""
    ensure_bridge_running()
    payload = {"phone": phone}
    try:
        r = requests.post(f"{BRIDGE_URL}/pairing-code", json=payload, timeout=20.0)
        return r.json()
    except Exception as e:
        return {"success": False, "error": f"Failed to request pairing code: {e}"}


def logout_bridge() -> dict[str, Any]:
    """Disconnect session and restart socket to generate fresh QR code."""
    try:
        r = requests.post(f"{BRIDGE_URL}/logout", timeout=5.0)
        return r.json()
    except Exception as e:
        return {"success": False, "error": str(e)}
