from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def reload_environment() -> None:
    """Reload environment variables from .env file."""
    if ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE, override=True)
    else:
        load_dotenv(override=True)


def _meta_settings() -> dict[str, Any]:
    """Read Meta WhatsApp Cloud API settings dynamically on each invocation."""
    reload_environment()
    phone_id = os.getenv("META_WA_PHONE_NUMBER_ID", "").strip()
    token = os.getenv("META_WA_ACCESS_TOKEN", "").strip()
    api_version = os.getenv("META_WA_API_VERSION", "v20.0").strip() or "v20.0"

    is_dummy = "testtoken" in token.lower() or (len(token) > 0 and len(token) < 30)
    is_configured = bool(phone_id and token and not is_dummy)
    return {
        "phone_number_id": phone_id,
        "access_token": token,
        "api_version": api_version,
        "configured": is_configured,
    }


def get_meta_whatsapp_status() -> dict[str, Any]:
    """Return sanitized configuration state for frontend display."""
    settings = _meta_settings()
    token = settings["access_token"]
    masked_token = (
        f"{token[:6]}••••••••{token[-4:]}"
        if len(token) > 12
        else ("••••••••" if token else "")
    )
    return {
        "configured": settings["configured"],
        "phone_number_id": settings["phone_number_id"],
        "has_token": bool(token),
        "token_preview": masked_token,
        "api_version": settings["api_version"],
    }


def save_meta_whatsapp_settings(
    phone_number_id: str,
    access_token: str | None = None,
    api_version: str = "v20.0",
) -> dict[str, Any]:
    """Persist Meta WhatsApp Cloud API credentials to .env file and reload environment."""
    phone_number_id = phone_number_id.strip()
    api_version = (api_version or "v20.0").strip()

    current_settings = _meta_settings()
    final_token = current_settings["access_token"]
    if access_token is not None:
        token_clean = access_token.strip()
        if not token_clean.startswith("••••"):
            final_token = token_clean

    existing_lines: list[str] = []
    if ENV_FILE.exists():
        try:
            existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        except Exception:
            existing_lines = []

    keys_to_set = {
        "META_WA_PHONE_NUMBER_ID": phone_number_id,
        "META_WA_ACCESS_TOKEN": final_token,
        "META_WA_API_VERSION": api_version,
    }

    found_keys = set()
    new_lines = []
    for line in existing_lines:
        line_clean = line.strip()
        matched_key = None
        for k in keys_to_set:
            if line_clean.startswith(f"{k}=") or line_clean == k:
                matched_key = k
                break

        if matched_key:
            found_keys.add(matched_key)
            new_lines.append(f"{matched_key}={keys_to_set[matched_key]}")
        else:
            new_lines.append(line)

    for k, val in keys_to_set.items():
        if k not in found_keys:
            new_lines.append(f"{k}={val}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    reload_environment()

    return {
        "success": True,
        "message": "Meta WhatsApp Cloud API settings saved successfully.",
        "config": get_meta_whatsapp_status(),
    }


def normalize_phone_number(raw_phone: str) -> str:
    """Normalize phone number to international E.164 digits without leading '+'."""
    digits = re.sub(r"\D", "", raw_phone or "")
    if digits.startswith("0") and len(digits) == 11:  # e.g., PK 03001234567 -> 923001234567
        digits = "92" + digits[1:]
    elif len(digits) == 10 and digits.startswith("3"):  # e.g., 3001234567 -> 923001234567
        digits = "92" + digits
    return digits


def upload_media_to_meta(
    pdf_bytes: bytes,
    filename: str = "E-Challan.pdf",
) -> dict[str, Any]:
    """Upload raw binary PDF to Meta's WhatsApp Media API and retrieve media ID."""
    settings = _meta_settings()
    if not settings["configured"]:
        return {
            "success": False,
            "error": "Meta WhatsApp Cloud API is not configured. Please set Phone Number ID and Access Token.",
        }

    phone_id = settings["phone_number_id"]
    token = settings["access_token"]
    api_version = settings["api_version"]
    url = f"https://graph.facebook.com/{api_version}/{phone_id}/media"

    headers = {
        "Authorization": f"Bearer {token}",
    }

    files = {
        "file": (filename, io.BytesIO(pdf_bytes), "application/pdf"),
    }
    data = {
        "messaging_product": "whatsapp",
        "type": "application/pdf",
    }

    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if resp.status_code in (200, 201):
            res_json = resp.json()
            media_id = res_json.get("id")
            return {"success": True, "media_id": media_id}
        else:
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = err_data.get("error", {}).get("message") or resp.text
            return {
                "success": False,
                "error": f"Meta Media Upload Failed ({resp.status_code}): {err_msg}",
            }
    except Exception as e:
        return {"success": False, "error": f"Connection error uploading PDF to Meta: {str(e)}"}


def send_meta_whatsapp_document(
    to_phone: str,
    pdf_bytes: bytes,
    filename: str = "Official_E_Challan.pdf",
    caption: str | None = None,
) -> dict[str, Any]:
    """Upload PDF and send it as a real WhatsApp document directly to the recipient's phone number."""
    settings = _meta_settings()
    if not settings["configured"]:
        return {
            "success": False,
            "error": "Meta WhatsApp Cloud API is not configured. Please configure your Phone Number ID and Access Token.",
        }

    recipient = normalize_phone_number(to_phone)
    if not recipient:
        return {"success": False, "error": "Invalid recipient phone number."}

    # 1. Upload media directly to Meta
    upload_res = upload_media_to_meta(pdf_bytes, filename=filename)
    if not upload_res["success"]:
        return upload_res

    media_id = upload_res["media_id"]

    # 2. Dispatch document message via Meta Messages API
    phone_id = settings["phone_number_id"]
    token = settings["access_token"]
    api_version = settings["api_version"]
    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
        },
    }

    if caption:
        payload["document"]["caption"] = caption

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code in (200, 201):
            res_json = resp.json()
            msg_id = res_json.get("messages", [{}])[0].get("id", "")
            return {
                "success": True,
                "message_id": msg_id,
                "media_id": media_id,
                "recipient": recipient,
                "message": f"Official PDF document sent successfully to +{recipient} via WhatsApp Cloud API!",
            }
        else:
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = err_data.get("error", {}).get("message") or resp.text
            return {
                "success": False,
                "error": f"Meta WhatsApp API Error ({resp.status_code}): {err_msg}",
            }
    except Exception as e:
        return {"success": False, "error": f"Connection error communicating with Meta: {str(e)}"}


def send_meta_whatsapp_text(
    to_phone: str,
    message_text: str,
) -> dict[str, Any]:
    """Send formatted text message directly via Meta WhatsApp Cloud API."""
    settings = _meta_settings()
    if not settings["configured"]:
        return {
            "success": False,
            "error": "Meta WhatsApp Cloud API is not configured.",
        }

    recipient = normalize_phone_number(to_phone)
    if not recipient:
        return {"success": False, "error": "Invalid recipient phone number."}

    phone_id = settings["phone_number_id"]
    token = settings["access_token"]
    api_version = settings["api_version"]
    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": message_text,
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code in (200, 201):
            res_json = resp.json()
            msg_id = res_json.get("messages", [{}])[0].get("id", "")
            return {
                "success": True,
                "message_id": msg_id,
                "recipient": recipient,
                "message": f"Official notice text delivered to +{recipient} via WhatsApp Cloud API!",
            }
        else:
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = err_data.get("error", {}).get("message") or resp.text
            return {
                "success": False,
                "error": f"Meta WhatsApp API Error ({resp.status_code}): {err_msg}",
            }
    except Exception as e:
        return {"success": False, "error": f"Connection error communicating with Meta: {str(e)}"}


def send_meta_whatsapp_test(to_phone: str) -> dict[str, Any]:
    """Send a diagnostic test message to verify token and phone connectivity."""
    test_msg = (
        "✅ *ANPR Command Center — Meta WhatsApp API Test*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "This is an automated diagnostic verification message.\n"
        "Your WhatsApp Business Cloud API is active, authenticated, and ready for official PDF dispatch!"
    )
    return send_meta_whatsapp_text(to_phone, test_msg)
