from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Set

import cv2
import numpy as np
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CAMERA_AREAS, PROJECT_ROOT, get_local_now, settings
from .detectors import detectors
from .mailer import (
    format_whatsapp_message,
    generate_email_html,
    generate_whatsapp_url,
    get_smtp_config_status,
    save_smtp_settings_to_env,
    send_email_notification,
    send_test_email,
)
from .whatsapp_meta import (
    get_meta_whatsapp_status,
    save_meta_whatsapp_settings,
    send_meta_whatsapp_document,
    send_meta_whatsapp_text,
    send_meta_whatsapp_test,
    _meta_settings,
)
from .whatsapp_bridge import (
    get_bridge_status,
    send_bridge_document,
    send_bridge_text,
    logout_bridge,
    request_pairing_code,
)
from .models import (
    AdminLoginRequest,
    AdminLoginResponse,
    ApprovedVehicleCreate,
    ApprovedVehicleUpdate,
    FrameResponse,
    MetaWhatsAppConfigRequest,
    SMTPConfigRequest,
    TestEmailRequest,
    TestWhatsAppRequest,
    ViolationNotificationRequest,
)
from .pdf_generator import generate_challan_pdf_bytes
from .storage import store

ADMIN_EMAIL = "admin@anpr.gov"
ADMIN_PASSWORD = "admin123"


class LiveBroadcaster:
    """Manages active WebSockets and broadcasts live camera frames & detections in real-time."""

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self.latest_frame: dict | None = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        # Send latest frame immediately upon connection if available
        if self.latest_frame:
            try:
                await websocket.send_json(self.latest_frame)
            except Exception:
                pass

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, frame_data: dict) -> None:
        self.latest_frame = frame_data
        async with self._lock:
            sockets = list(self.active_connections)
        dead_sockets = []
        for ws in sockets:
            try:
                await ws.send_json(frame_data)
            except Exception:
                dead_sockets.append(ws)
        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    if ws in self.active_connections:
                        self.active_connections.remove(ws)


live_broadcaster = LiveBroadcaster()

app = FastAPI(title="Just Meter - AJK Government Car Surveillance System", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/snapshots", StaticFiles(directory=settings.snapshots_dir), name="snapshots")

# Frontend static files mount (if built)
dist_dir = PROJECT_ROOT / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")
    app.mount("/app", StaticFiles(directory=dist_dir, html=True), name="frontend")


@app.get("/portal", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
def admin_portal() -> FileResponse:
    index_file = dist_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return FileResponse(PROJECT_ROOT / "phone" / "camera.html")



def decode_image(contents: bytes) -> np.ndarray:
    frame = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("The uploaded file is not a valid image")
    return frame


def vehicle_for_plate(vehicles: list[dict], plate_bbox: list[int]) -> str | None:
    """Choose the vehicle whose box contains the plate centre, when available."""
    px = (plate_bbox[0] + plate_bbox[2]) / 2
    py = (plate_bbox[1] + plate_bbox[3]) / 2
    for vehicle in vehicles:
        x1, y1, x2, y2 = vehicle["bbox"]
        if x1 <= px <= x2 and y1 <= py <= y2:
            return vehicle["label"]
    return None


def assess_compliance(record: dict[str, str], camera_area: str) -> dict[str, str]:
    """Assess an approved vehicle using the register's area and duty policy."""
    authorized_areas = {area.strip() for area in record["authorized_areas"].split("|") if area.strip()}
    if camera_area not in authorized_areas:
        return {"status": "VIOLATION", "violation_criteria": "UNAUTHORIZED_AREA"}

    schedule = record["duty_schedule"].strip().upper()
    if schedule == "24/7":
        return {"status": "LAWFUL", "violation_criteria": ""}
    try:
        start_text, end_text = schedule.split("-", 1)
        start = datetime.strptime(start_text.strip(), "%H:%M").time()
        end = datetime.strptime(end_text.strip(), "%H:%M").time()
        observed = get_local_now().time()
    except ValueError:
        return {"status": "VIOLATION", "violation_criteria": "INVALID_DUTY_SCHEDULE"}

    is_on_duty = start <= observed <= end if start <= end else observed >= start or observed <= end
    return {"status": "LAWFUL" if is_on_duty else "VIOLATION",
            "violation_criteria": "" if is_on_duty else "OUTSIDE_DUTY_HOURS"}


@app.get("/", include_in_schema=False)
def phone_camera() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "phone" / "camera.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "minimum_plate_confidence": settings.min_plate_confidence,
            "camera_areas": CAMERA_AREAS}


@app.get("/camera-areas")
def camera_areas() -> list[str]:
    return list(CAMERA_AREAS)


# ==========================================
# AUTHENTICATION API
# ==========================================
@app.post("/api/auth/login")
def admin_login(req: AdminLoginRequest) -> dict:
    email = req.email.strip().lower()
    valid_admin_emails = {ADMIN_EMAIL.lower(), "admin@justmeter.gov", "admin@justmeter.pk"}
    if email in valid_admin_emails and req.password == ADMIN_PASSWORD:
        return {
            "success": True,
            "token": "admin-session-token-valid",
            "user": {
                "email": email,
                "name": "System Administrator",
                "role": "Super Admin",
            },
        }
    raise HTTPException(401, "Invalid email or password")


# ==========================================
# AUTHORIZED VEHICLES CRUD API
# ==========================================
@app.get("/api/authorized-vehicles")
def list_authorized_vehicles(query: str | None = None, area: str | None = None) -> list[dict]:
    return store.get_all_approved_vehicles(query=query, area=area)


@app.post("/api/authorized-vehicles", status_code=201)
def create_authorized_vehicle(vehicle: ApprovedVehicleCreate) -> dict:
    success, error = store.add_approved_vehicle(vehicle.dict())
    if not success:
        raise HTTPException(400, error or "Could not add vehicle")
    return {"success": True, "message": "Vehicle added successfully", "vehicle": vehicle.dict()}


@app.put("/api/authorized-vehicles/{plate_number}")
def update_authorized_vehicle(plate_number: str, vehicle: ApprovedVehicleUpdate) -> dict:
    update_data = {k: v for k, v in vehicle.dict().items() if v is not None}
    success, error = store.update_approved_vehicle(plate_number, update_data)
    if not success:
        raise HTTPException(400, error or "Could not update vehicle")
    return {"success": True, "message": "Vehicle updated successfully"}


@app.delete("/api/authorized-vehicles/{plate_number}")
def delete_authorized_vehicle(plate_number: str) -> dict:
    success, error = store.delete_approved_vehicle(plate_number)
    if not success:
        raise HTTPException(404, error or "Vehicle not found")
    return {"success": True, "message": "Vehicle removed successfully"}


# ==========================================
# DETECTIONS & SIGHTINGS API
# ==========================================
@app.get("/api/stats")
def get_stats() -> dict:
    return store.get_system_stats()


@app.get("/api/government-vehicles-spotted")
def government_vehicle_api_history(limit: int = 1000) -> list[dict]:
    return store.latest_government_sightings(limit)


@app.post("/camera/frame", response_model=FrameResponse)
async def receive_frame(
    file: UploadFile = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location_accuracy_m: float | None = Form(None),
    camera_area: str = Form(...),
) -> dict:
    if camera_area not in CAMERA_AREAS:
        raise HTTPException(400, "Select a valid camera area")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG, or WebP camera frame")
    contents = await file.read(settings.max_upload_bytes + 1)
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(413, "Frame exceeds the maximum upload size")
    try:
        frame = decode_image(contents)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    vehicles, raw_plates = await asyncio.to_thread(detectors.detect, frame)
    plates = []
    for plate in raw_plates:
        if plate["confidence"] < settings.min_plate_confidence:
            plates.append({**plate, "saved": False, "reason": "below confidence threshold"})
            continue
        approved_vehicle = await asyncio.to_thread(store.find_approved_vehicle, plate["plate_number"])
        compliance = assess_compliance(approved_vehicle, camera_area) if approved_vehicle else None
        saved, reason = await asyncio.to_thread(
            store.save, frame, plate, latitude, longitude, location_accuracy_m,
            vehicle_for_plate(vehicles, plate["bbox"]), camera_area, approved_vehicle, compliance,
        )
        plates.append({**plate, "saved": saved, "reason": reason,
                       "government_match": approved_vehicle, "compliance": compliance})

    h, w = frame.shape[:2]
    # Fast lightweight preview compression for low latency WebSocket delivery
    max_preview_w = 800
    if w > max_preview_w:
        scale = max_preview_w / w
        preview_frame = cv2.resize(frame, (max_preview_w, int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        preview_frame = frame

    _, buffer = cv2.imencode(".jpg", preview_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
    img_base64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

    response_data = {
        "timestamp": get_local_now().isoformat(),
        "camera_area": camera_area,
        "latitude": latitude,
        "longitude": longitude,
        "frame_width": w,
        "frame_height": h,
        "image_data": img_base64,
        "vehicles": vehicles,
        "plates": plates,
    }

    # Broadcast frame in real-time to all connected Web App dashboards
    asyncio.create_task(live_broadcaster.broadcast(response_data))

    return response_data


@app.post("/api/camera/analyze", response_model=FrameResponse)
async def analyze_camera_frame(
    file: UploadFile = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location_accuracy_m: float | None = Form(None),
    camera_area: str = Form("Mzd. Division"),
) -> dict:
    """Analyze a frame directly from web app camera or local stream."""
    return await receive_frame(
        file=file,
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=location_accuracy_m,
        camera_area=camera_area,
    )


@app.get("/api/live-camera/latest")
def get_latest_live_frame() -> dict:
    """Retrieve the most recent frame processed by any connected scanner."""
    if live_broadcaster.latest_frame:
        return {"active": True, **live_broadcaster.latest_frame}
    return {"active": False, "message": "No live frames captured yet"}


@app.websocket("/ws/live-camera")
async def websocket_live_camera(websocket: WebSocket) -> None:
    """Real-time WebSocket feed streaming live vehicle & plate detections."""
    await live_broadcaster.connect(websocket)
    try:
        while True:
            # Keep socket open and handle ping / messages from web app
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await live_broadcaster.disconnect(websocket)
    except Exception:
        await live_broadcaster.disconnect(websocket)


# ==========================================
# VIOLATIONS & E-CHALLAN MANAGEMENT API
# ==========================================
@app.get("/api/violations-summary")
def get_violations_summary(query: str | None = None, stage: str | None = None) -> list[dict]:
    """Return aggregated violations list with warning/challan escalation status."""
    return store.get_violations_summary(query=query, stage=stage)


@app.get("/api/challan/pdf/{plate_number}")
def download_challan_pdf(plate_number: str) -> Response:
    """Generate and return official downloadable/printable E-Challan PDF."""
    challan = store.get_vehicle_challan_data(plate_number)
    if not challan:
        raise HTTPException(404, f"No violations or challan found for vehicle '{plate_number}'")
    pdf_bytes = generate_challan_pdf_bytes(challan)
    cid = challan.get("challan_id") or f"CHL-2026-{plate_number}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=E-Challan_{cid}.pdf",
            "Cache-Control": "no-cache",
        },
    )


@app.get("/api/challan/{plate_number}")
def get_challan_for_vehicle(plate_number: str) -> dict:
    """Retrieve full challan details and violation breakdown for a vehicle."""
    challan = store.get_vehicle_challan_data(plate_number)
    if not challan:
        raise HTTPException(404, f"No violations or challan found for vehicle '{plate_number}'")
    return challan



# ==========================================
# WHATSAPP QR GATEWAY & CLOUD API ENDPOINTS
# ==========================================
@app.get("/api/whatsapp-gateway/status")
def get_whatsapp_gateway_status_endpoint() -> dict:
    """Retrieve active local WhatsApp Web bridge connection state and QR code."""
    return get_bridge_status()


@app.post("/api/whatsapp-gateway/logout")
def logout_whatsapp_gateway_endpoint() -> dict:
    """Disconnect session and restart socket to generate fresh QR code."""
    return logout_bridge()


@app.post("/api/whatsapp-gateway/pair-code")
def request_whatsapp_pairing_code_endpoint(req: dict) -> dict:
    """Request an 8-digit pairing code to link phone without scanning QR."""
    phone = req.get("phone", "")
    if not phone:
        raise HTTPException(400, "Phone number is required.")
    res = request_pairing_code(phone)
    if not res.get("success"):
        raise HTTPException(400, res.get("error", "Failed to generate pairing code."))
    return res


@app.get("/api/settings/whatsapp")
def get_meta_whatsapp_settings_endpoint() -> dict:
    """Retrieve current Meta WhatsApp Cloud API status (token masked)."""
    return get_meta_whatsapp_status()


@app.post("/api/settings/whatsapp")
def update_meta_whatsapp_settings_endpoint(req: MetaWhatsAppConfigRequest) -> dict:
    """Save Meta WhatsApp Cloud API configuration to .env and apply immediately."""
    return save_meta_whatsapp_settings(
        phone_number_id=req.phone_number_id,
        access_token=req.access_token,
        api_version=req.api_version,
    )


@app.post("/api/settings/whatsapp/test")
def test_meta_whatsapp_endpoint(req: TestWhatsAppRequest) -> dict:
    """Send a diagnostic test message via Meta WhatsApp Cloud API."""
    if req.config:
        save_meta_whatsapp_settings(
            phone_number_id=req.config.phone_number_id,
            access_token=req.config.access_token,
            api_version=req.config.api_version,
        )
    result = send_meta_whatsapp_test(req.recipient_phone)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Failed to send WhatsApp test message."))
    return result


# ==========================================
# SMTP & SYSTEM CONFIGURATION API
# ==========================================
@app.get("/api/settings/smtp")
def get_smtp_settings_endpoint() -> dict:
    """Retrieve current SMTP configuration status (passwords masked)."""
    return get_smtp_config_status()


@app.post("/api/settings/smtp")
def update_smtp_settings_endpoint(req: SMTPConfigRequest) -> dict:
    """Save SMTP configuration to .env and apply immediately in runtime."""
    res = save_smtp_settings_to_env(
        host=req.host,
        port=req.port,
        user=req.user,
        password=req.password,
        sender_email=req.sender_email,
        sender_name=req.sender_name,
        use_tls=req.use_tls,
        use_ssl=req.use_ssl,
    )
    return res


@app.post("/api/settings/smtp/test")
def test_smtp_endpoint(req: TestEmailRequest) -> dict:
    """Send a diagnostic test email to verify SMTP configuration."""
    custom_cfg = None
    if req.config:
        custom_cfg = {
            "host": req.config.host,
            "port": req.config.port,
            "user": req.config.user,
            "password": req.config.password,
            "sender_email": req.config.sender_email or req.config.user,
            "sender_name": req.config.sender_name or "ANPR Fleet Command",
            "use_tls": req.config.use_tls,
            "use_ssl": req.config.use_ssl,
        }
    result = send_test_email(req.recipient_email, custom_config=custom_cfg)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Failed to dispatch test email."))
    return result


@app.post("/api/send-notification")
def dispatch_violation_notification(req: ViolationNotificationRequest) -> dict:
    """Dispatch official warning or e-challan notice via Local WhatsApp Bridge (Direct PDF/Text), Meta API, or WhatsApp URL."""
    challan_data = store.get_vehicle_challan_data(req.plate_number)
    history = challan_data.get("violations_history", []) if challan_data else []
    officer = req.officer_name or (challan_data.get("officer_name") if challan_data else "")
    phone = req.recipient_phone or (challan_data.get("officer_phone") if challan_data else "")
    email = req.recipient_email or (challan_data.get("officer_email") if challan_data else "")
    dept = challan_data.get("department", "Government Fleet") if challan_data else "Government Fleet"
    v_count = req.violation_count or (challan_data.get("total_violations", 1) if challan_data else 1)
    fine = req.fine_amount if req.fine_amount is not None else (challan_data.get("fine_amount", 0) if challan_data else 0)
    cid = req.challan_id or (challan_data.get("challan_id") if challan_data else None)

    # Ensure complete challan_data structure
    if not challan_data:
        challan_data = {
            "plate_number": req.plate_number,
            "normalized_plate": req.plate_number.replace("-", "").upper(),
            "department": dept,
            "vehicle_id": "GOV-" + req.plate_number.replace("-", ""),
            "officer_name": officer,
            "officer_phone": phone,
            "officer_email": email,
            "authorized_areas": "All Operational Areas",
            "duty_schedule": "24/7",
            "total_violations": v_count,
            "fine_amount": fine,
            "challan_id": cid or f"CHL-2026-{req.plate_number.replace('-', '')}-{v_count}",
            "violations_history": history,
            "status": "CHALLAN_ISSUED" if (req.message_type == "challan" or v_count >= 4) else "WARNING",
            "issue_date": get_local_now().strftime("%Y-%m-%d %I:%M:%S %p"),
        }

    # Format WhatsApp message & fallback URL
    wa_text = format_whatsapp_message(
        plate_number=req.plate_number,
        officer_name=officer,
        department=dept,
        violation_count=v_count,
        message_type=req.message_type,
        fine_amount=fine,
        challan_id=cid,
        custom_message=req.custom_message,
    )
    wa_url = generate_whatsapp_url(phone, wa_text)

    result = {
        "success": True,
        "channel": req.channel,
        "plate_number": req.plate_number,
        "officer_name": officer,
        "recipient_phone": phone,
        "recipient_email": email,
        "whatsapp_url": wa_url,
        "whatsapp_message": wa_text,
        "bridge_dispatched": False,
        "meta_dispatched": False,
        "email_dispatched": False,
        "message": "Notification link generated successfully.",
    }

    # 1. Check Local WhatsApp Web QR Bridge First (Direct PDF/Text from user's scanned phone)
    bridge_info = get_bridge_status()
    is_bridge_ready = bool(bridge_info.get("connected"))

    if (req.channel in ("whatsapp_direct", "whatsapp") and is_bridge_ready and phone):
        if req.message_type == "challan" or v_count >= 4:
            pdf_bytes = generate_challan_pdf_bytes(challan_data)
            caption_text = f"🚨 *Official Government E-Challan Notice: {req.plate_number}*\nPenalty Levied: PKR {int(fine):,}\nPSID / 1Bill: {cid or req.plate_number}"
            b_res = send_bridge_document(
                to_phone=phone,
                pdf_bytes=pdf_bytes,
                filename=f"E-Challan_{cid or req.plate_number}.pdf",
                caption=caption_text,
            )
            result["bridge_result"] = b_res
            result["bridge_dispatched"] = b_res.get("success", False)
            if b_res.get("success"):
                result["message"] = b_res.get("message")
                return result
            elif req.channel == "whatsapp_direct":
                raise HTTPException(400, b_res.get("error", "Failed to dispatch PDF via WhatsApp Bridge."))
        else:
            b_res = send_bridge_text(to_phone=phone, message=wa_text)
            result["bridge_result"] = b_res
            result["bridge_dispatched"] = b_res.get("success", False)
            if b_res.get("success"):
                result["message"] = b_res.get("message")
                return result
            elif req.channel == "whatsapp_direct":
                raise HTTPException(400, b_res.get("error", "Failed to dispatch WhatsApp notice via Bridge."))

    # 2. Fallback to Direct Meta WhatsApp Cloud API Dispatch
    meta_cfg = _meta_settings()
    if (req.channel == "whatsapp_direct") or (req.channel == "whatsapp" and meta_cfg["configured"] and phone):
        if not phone:
            raise HTTPException(400, "Recipient mobile number is required for direct WhatsApp dispatch.")
        if not meta_cfg["configured"] and not is_bridge_ready and req.channel == "whatsapp_direct":
            raise HTTPException(400, "WhatsApp QR Bridge is not connected. Please scan the QR code in the WhatsApp Gateway modal.")

        if meta_cfg["configured"]:
            if req.message_type == "challan" or v_count >= 4:
                pdf_bytes = generate_challan_pdf_bytes(challan_data)
                caption_text = f"🚨 *Official Government E-Challan Notice: {req.plate_number}*\nPenalty Levied: PKR {int(fine):,}\nPSID / 1Bill: {cid or req.plate_number}"
                meta_res = send_meta_whatsapp_document(
                    to_phone=phone,
                    pdf_bytes=pdf_bytes,
                    filename=f"E-Challan_{cid or req.plate_number}.pdf",
                    caption=caption_text,
                )
                result["meta_result"] = meta_res
                result["meta_dispatched"] = meta_res.get("success", False)
                if meta_res.get("success"):
                    result["message"] = meta_res.get("message")
                elif req.channel == "whatsapp_direct":
                    raise HTTPException(400, meta_res.get("error", "Failed to dispatch PDF via Meta WhatsApp Cloud API."))
            else:
                meta_res = send_meta_whatsapp_text(to_phone=phone, message_text=wa_text)
                result["meta_result"] = meta_res
                result["meta_dispatched"] = meta_res.get("success", False)
                if meta_res.get("success"):
                    result["message"] = meta_res.get("message")
                elif req.channel == "whatsapp_direct":
                    raise HTTPException(400, meta_res.get("error", "Failed to dispatch WhatsApp notice."))

    # Optional Email dispatch
    if req.channel == "email":
        if not email:
            raise HTTPException(400, "Recipient email address is required for Email dispatch.")
        subject = (
            f"🚨 OFFICIAL TRAFFIC CHALLAN [{cid or req.plate_number}] - Govt Fleet Command"
            if req.message_type == "challan" or v_count >= 4
            else f"⚠️ Official Fleet Warning #{v_count} - Vehicle {req.plate_number}"
        )
        html = generate_email_html(
            plate_number=req.plate_number,
            officer_name=officer,
            department=dept,
            violation_count=v_count,
            message_type=req.message_type,
            violations_history=history,
            fine_amount=fine,
            challan_id=cid,
            custom_message=req.custom_message,
        )
        pdf_bytes = (
            generate_challan_pdf_bytes(challan_data)
            if (req.message_type == "challan" or v_count >= 4) and challan_data
            else None
        )
        email_res = send_email_notification(
            recipient_email=email,
            subject=subject,
            html_content=html,
            plain_text=wa_text,
            pdf_attachment=pdf_bytes,
            attachment_filename=f"E-Challan_{cid or req.plate_number}.pdf",
        )
        result["email_result"] = email_res
        result["email_dispatched"] = email_res.get("success", False)
        result["message"] = email_res.get("message") or email_res.get("error", "Email processed.")
        if not email_res.get("success"):
            raise HTTPException(400, email_res.get("error", "Failed to dispatch official email."))

    return result


@app.get("/detections")
def detection_history(limit: int = 100) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    return store.latest(limit)


@app.get("/government-vehicles-spotted")
def government_vehicle_history(limit: int = 100) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    return store.latest_government_sightings(limit)


