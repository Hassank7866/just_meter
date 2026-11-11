from __future__ import annotations

import asyncio
import base64
import io
import json
from datetime import date, datetime
from pathlib import Path
import tempfile
import zipfile
from typing import Set
from threading import Lock
from uuid import uuid4

import cv2
import numpy as np
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import CAMERA_AREAS, PROJECT_ROOT, get_local_now, settings
from .auth import OFFICER_ROLES, authenticate, create_access_token, create_camera_token, create_live_feed_token, decode_access_token, token_from_request
from .escalation import is_challan_stage
from .risk_engine import RiskPolicyConfig
from pydantic import BaseModel
from .anpr import analyze_plate_text, is_valid_plate, normalize_plate_text
from .compliance_engine import evaluate_compliance
from .geofencing import validate_geofence
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
    EvidenceReviewRequest,
    FrameResponse,
    MetaWhatsAppConfigRequest,
    PlateReviewRequest,
    SMTPConfigRequest,
    TestEmailRequest,
    TestWhatsAppRequest,
    VideoAnalysisResponse,
    ViolationNotificationRequest,
)
from .pdf_generator import generate_challan_pdf_bytes
from .storage import store
from .vims_api import create_vims_router
from .duty_api import create_duty_router
from .digital_twin_api import create_digital_twin_router
from .challan_api import create_challan_router
from .duty_verification import merge_duty
from .access import principal_context, scoped_department, snapshot_allowed, require_vehicle
from .movement_api import create_movement_router
from .route_api import create_route_router
from .verification_api import create_verification_router
from .db_models import Department
from .audit import log_access
from .governance_api import create_governance_router
from .tracking_api import create_tracking_router

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
                principal = await asyncio.to_thread(decode_access_token, ws.query_params.get("token", ""), store.engine)
                if principal["role"] != "Administrator" or principal.get("scope") != "live_feed":
                    raise HTTPException(401, "Session revoked")
                await ws.send_json(frame_data)
            except Exception:
                dead_sockets.append(ws)
                try:
                    await ws.close(code=1008, reason="Session expired or revoked")
                except Exception:
                    pass
        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    if ws in self.active_connections:
                        self.active_connections.remove(ws)


live_broadcaster = LiveBroadcaster()
def _get_geofences() -> list[dict]:
    return store.get_geofences()


def _save_geofences(zones: list[dict]) -> None:
    store.save_geofences(zones)


app = FastAPI(title="Just Meter - AJK Government Car Surveillance System", version="1.0.0")
app.include_router(create_vims_router(lambda: store))
app.include_router(create_duty_router(lambda: store))
app.include_router(create_digital_twin_router(lambda: store))
app.include_router(create_challan_router(lambda: store))
app.include_router(create_governance_router(lambda: store))
app.include_router(create_tracking_router(lambda: store))
app.include_router(create_movement_router(lambda: store))
app.include_router(create_route_router(lambda: store))
app.include_router(create_verification_router(lambda: store))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/snapshots", StaticFiles(directory=settings.snapshots_dir), name="snapshots")


def _roles_for_request(method: str, path: str) -> set[str]:
    """Central role policy: auditors can read; officers can operate; admin configures."""
    method = method.upper()
    if path in {"/api/auth/me", "/api/auth/logout", "/api/departments"}:
        return {"Administrator", "Transport Officer", "Supervisory Officer", "Auditor"}
    if path.startswith("/api/reports/") and method == "GET":
        return {"Administrator", "Transport Officer", "Supervisory Officer", "Auditor"}
    if path.startswith("/api/vehicles/") and path.endswith("/movement-trail") and method == "GET":
        return {"Administrator", "Transport Officer", "Supervisory Officer", "Auditor"}
    if method == "GET" and (path == "/api/vehicle-verification/risk-queue" or
                            (path.startswith("/api/vehicles/") and path.endswith("/verifications"))):
        return {"Administrator", "Transport Officer", "Supervisory Officer", "Auditor"}
    if path == "/api/audit" and method == "GET":
        return {"Administrator", "Supervisory Officer", "Auditor"}
    if path.startswith(("/api/users", "/api/settings/", "/api/whatsapp-gateway/", "/api/vims/", "/api/geofences", "/api/approved-routes")):
        return {"Administrator"}
    if path.startswith(("/api/camera/", "/api/live-camera/", "/api/vehicle-tracks",
                        "/api/camera-checkpoints/", "/api/checkpoint-crossings", "/api/track-links")) or path == "/api/vehicle-detection-events":
        return {"Administrator"}
    if path == "/api/send-notification":
        return {"Administrator", "Supervisory Officer"}
    if path.startswith("/api/duty/observations/") and method == "POST":
        return {"Administrator", "Supervisory Officer"}
    if path == "/api/live-camera/session-token" and method == "POST":
        return {"Administrator", "Transport Officer", "Supervisory Officer", "Auditor"}
    admin_only = (
        path.startswith("/api/duty/coverage/") and method not in {"GET", "HEAD", "OPTIONS"}
        or
        path.startswith("/api/vims/") and method not in {"GET", "HEAD", "OPTIONS"}
        or path == "/api/risk/policy" and method not in {"GET", "HEAD", "OPTIONS"}
        or path.startswith("/api/authorized-vehicles") and method not in {"GET", "HEAD", "OPTIONS"}
        or path.startswith("/api/geofences") and method not in {"GET", "HEAD", "OPTIONS"}
        or path.startswith("/api/settings/") and method not in {"GET", "HEAD", "OPTIONS"}
        or path.startswith("/api/whatsapp-gateway/") and method not in {"GET", "HEAD", "OPTIONS"}
    )
    if admin_only:
        return {"Administrator"}
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return OFFICER_ROLES
    return {"Administrator", "Transport Officer", "Supervisory Officer"}


@app.middleware("http")
async def enforce_api_authentication(request: Request, call_next):
    path = request.url.path
    protected_api = path.startswith("/api/") or path in {"/detections", "/government-vehicles-spotted"}
    protected_upload = path == "/camera/frame"
    protected_snapshots = path == "/snapshots" or path.startswith("/snapshots/")
    if not (protected_api or protected_upload or protected_snapshots):
        return await call_next(request)
    if path == "/api/auth/login":
        return await call_next(request)

    async def reject(status, message, principal=None):
        await asyncio.to_thread(log_access, store.engine, (principal or {}).get("sub", "anonymous"),
                                "ACCESS_DENIED", path, status, (principal or {}).get("department_id"), method=request.method)
        return JSONResponse(status_code=status, content={"detail": message})

    token = token_from_request(request)
    if not token:
        return await reject(401, "Authentication required")
    try:
        principal = await asyncio.to_thread(decode_access_token, token, store.engine)
    except HTTPException as exc:
        return await reject(exc.status_code, exc.detail)

    if principal.get("scope") and (not protected_upload or principal["scope"] != "camera_upload"):
        return await reject(401, "This token is restricted to mobile camera uploads", principal)

    if protected_api:
        allowed = _roles_for_request(request.method, path)
        if principal["role"] not in allowed:
            return await reject(403, "Your role is not allowed to perform this action", principal)
    elif (protected_upload and principal["role"] != "Administrator") or (protected_snapshots and principal["role"] == "Auditor"):
        return await reject(403, "Your role is not allowed to access raw camera data", principal)

    if principal["role"] == "Auditor" and not protected_api:
        return await reject(403, "Auditors can access reports and audit history", principal)

    request.state.principal = principal
    context_token = principal_context.set(principal)
    status = 500
    try:
        if protected_snapshots and not await asyncio.to_thread(snapshot_allowed, store, path.removeprefix("/snapshots/")):
            status = 404
            return JSONResponse(status_code=404, content={"detail": "Image not found"})
        response = await call_next(request)
        status = response.status_code
        response.headers["Cache-Control"] = "private, no-store"
        return response
    finally:
        await asyncio.to_thread(log_access, store.engine, principal["sub"],
                                "ACCESS" if status < 400 else "ACCESS_DENIED", path, status,
                                principal.get("department_id"), method=request.method)
        principal_context.reset(context_token)

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


def matched_vehicle_for_plate(vehicles: list[dict], plate_bbox: list[int]) -> dict | None:
    """Choose the smallest containing vehicle box for an observed plate."""
    px = (plate_bbox[0] + plate_bbox[2]) / 2
    py = (plate_bbox[1] + plate_bbox[3]) / 2
    candidates = []
    for vehicle in vehicles:
        x1, y1, x2, y2 = vehicle["bbox"]
        if x1 <= px <= x2 and y1 <= py <= y2:
            candidates.append(vehicle)
    return min(candidates, key=lambda item: (item["bbox"][2] - item["bbox"][0]) *
               (item["bbox"][3] - item["bbox"][1])) if candidates else None


def vehicle_for_plate(vehicles: list[dict], plate_bbox: list[int]) -> str | None:
    match = matched_vehicle_for_plate(vehicles, plate_bbox)
    return match["label"] if match else None


def assess_compliance(
    record: dict[str, str] | None,
    camera_area: str,
    observed_at: datetime | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """Compatibility wrapper around the explainable compliance decision engine."""
    observed_at = observed_at or get_local_now()
    if not record:
        return evaluate_compliance(record, camera_area, observed_at, latitude, longitude, _get_geofences())
    duty = store.verify_vehicle_duty(record["plate_number"], observed_at, camera_area)
    route = store.route_context_for_plate(record["plate_number"], observed_at, duty)
    base = evaluate_compliance(record, camera_area, observed_at, latitude, longitude,
                               _get_geofences(), route, duty)
    return merge_duty(base, duty)


@app.get("/", include_in_schema=False)
def phone_camera() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "phone" / "camera.html")


@app.get("/health")
def health() -> dict:
    from sqlalchemy import text
    from .database import get_engine
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database is unavailable") from None
    return {"status": "ok", "database": "connected", "minimum_plate_confidence": settings.min_plate_confidence,
            "camera_areas": CAMERA_AREAS}


@app.get("/camera-areas")
def camera_areas() -> list[str]:
    return list(CAMERA_AREAS)


@app.post("/api/camera/session-token")
def create_mobile_camera_session(request: Request) -> dict:
    """Issue a short-lived, upload-only token for the paired mobile scanner."""
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.get("role") not in OFFICER_ROLES:
        raise HTTPException(403, "Your role is not allowed to operate a camera")
    return {"token": create_camera_token(principal), "expires_in": 1200}


@app.post("/api/live-camera/session-token")
def create_live_feed_session(request: Request) -> dict:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(401, "Authentication required")
    return {"token": create_live_feed_token(principal), "expires_in": 1200}


@app.get("/api/geofences")
def list_geofences() -> list[dict]:
    return _get_geofences()


@app.post("/api/geofences", status_code=201)
def create_geofence(payload: dict) -> dict:
    with store._lock as session:
        try:
            zone = validate_geofence(payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if zone["camera_area"] not in CAMERA_AREAS:
            raise HTTPException(400, "Select a configured camera area")
        if zone["department_id"] is not None and session.get(Department, zone["department_id"]) is None:
            raise HTTPException(400, "Select an existing department")
        zones = _get_geofences()
        zone["zone_id"] = f"GEO-{uuid4().hex[:10].upper()}"
        zones.append(zone)
        _save_geofences(zones)
        return zone


@app.put("/api/geofences/{zone_id}")
def update_geofence(zone_id: str, payload: dict) -> dict:
    with store._lock as session:
        try:
            zone = validate_geofence(payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if zone["camera_area"] not in CAMERA_AREAS:
            raise HTTPException(400, "Select a configured camera area")
        if zone["department_id"] is not None and session.get(Department, zone["department_id"]) is None:
            raise HTTPException(400, "Select an existing department")
        zones = _get_geofences()
        for index, existing in enumerate(zones):
            if existing.get("zone_id") == zone_id:
                zone["zone_id"] = zone_id
                zones[index] = zone
                _save_geofences(zones)
                return zone
        raise HTTPException(404, "Geofence not found")


@app.delete("/api/geofences/{zone_id}")
def delete_geofence(zone_id: str) -> dict:
    with store._lock:
        zones = _get_geofences()
        updated = [zone for zone in zones if zone.get("zone_id") != zone_id]
        if len(updated) == len(zones):
            raise HTTPException(404, "Geofence not found")
        _save_geofences(updated)
        return {"success": True}


# ==========================================
# AUTHENTICATION API
# ==========================================
@app.post("/api/auth/login")
def admin_login(req: AdminLoginRequest) -> dict:
    account = authenticate(req.email, req.password, store.engine)
    if account is None:
        log_access(store.engine, "anonymous", "LOGIN_FAILED", "session", 401)
        raise HTTPException(401, "Invalid email or password")
    log_access(store.engine, account["email"], "LOGIN", "session", 200, account.get("department_id"))
    user = {key: account[key] for key in ("email", "name", "role", "department_id")}
    return {"success": True, "token": create_access_token(account), "user": user}


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


@app.get("/api/dashboard")
def executive_dashboard(start_date: date | None = None, end_date: date | None = None,
                        department: str = "") -> dict:
    try:
        return store.get_executive_dashboard(start_date, end_date, department)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


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
    camera_id: str = Form("CAM-001"),
    frame_number: int | None = Form(None),
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
    h, w = frame.shape[:2]
    event = await asyncio.to_thread(
        store.save_vehicle_event, vehicles, camera_id.strip() or "CAM-001", camera_area,
        "LIVE_FRAME", w, h, frame_number,
    )
    vehicles = event["detections"]
    plates = []
    for plate in raw_plates:
        matched_vehicle = matched_vehicle_for_plate(vehicles, plate["bbox"])
        track_id = matched_vehicle.get("track_id", "") if matched_vehicle else ""
        analysis = analyze_plate_text(
            plate.get("raw_text") or plate["plate_number"],
            plate["confidence"], settings.min_plate_confidence,
        )
        recognition = await asyncio.to_thread(
            store.save_plate_recognition, frame, plate, analysis, event["event_id"],
            event["camera_id"], camera_area, track_id,
        )
        enriched_plate = {
            **plate,
            **analysis,
            "plate_number": analysis["final_text"] or analysis["normalized_text"],
            "recognition_id": recognition["recognition_id"],
            "plate_crop": recognition["plate_crop"],
            "track_id": track_id,
        }
        detected_vehicle_type = matched_vehicle["label"] if matched_vehicle else None
        if analysis["review_status"] != "ACCEPTED":
            review_decision = {
                "status": "REVIEW_REQUIRED",
                "violation_criteria": "",
                "decision_reason": "OCR confidence or plate format requires officer confirmation.",
                "rules": [{
                    "rule_id": "ANPR_CONFIDENCE",
                    "outcome": "REVIEW",
                    "message": analysis["review_reason"] or "Plate recognition requires review",
                }],
                "risk_score": 0,
                "risk_level": "PENDING_REVIEW",
                "risk_factors": [],
            }
            evidence = await asyncio.to_thread(
                store.save_evidence, frame, event, recognition, plate, latitude, longitude,
                detected_vehicle_type, None, None,
            )
            plates.append({**enriched_plate, "evidence_id": evidence["evidence_id"], "saved": False,
                           "reason": "manual review required", "compliance": review_decision})
            continue
        approved_vehicle = await asyncio.to_thread(store.find_approved_vehicle, analysis["final_text"])
        observed_at = datetime.fromisoformat(recognition["timestamp"])
        compliance = await asyncio.to_thread(assess_compliance, approved_vehicle, camera_area, observed_at, latitude, longitude)
        saved, reason = await asyncio.to_thread(
            store.save, frame, {
                **plate,
                "plate_number": analysis["final_text"],
                "recognition_id": recognition["recognition_id"],
                "track_id": track_id,
            },
            latitude, longitude, location_accuracy_m,
            detected_vehicle_type, camera_area, approved_vehicle, compliance, observed_at,
        )
        evidence_compliance = compliance
        if saved and compliance and compliance.get("status") == "VIOLATION":
            evidence_compliance = {
                **compliance,
                "violation_id": f"VIOL-{recognition['recognition_id']}",
            }
        evidence = await asyncio.to_thread(
            store.save_evidence, frame, event, recognition,
            {**plate, "recognition_id": recognition["recognition_id"]},
            latitude, longitude, detected_vehicle_type, approved_vehicle, evidence_compliance,
        )
        plates.append({**enriched_plate, "evidence_id": evidence["evidence_id"], "saved": saved, "reason": reason,
                       "government_match": approved_vehicle, "compliance": compliance})

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
        "event_id": event["event_id"],
        "timestamp": event["timestamp"],
        "camera_id": event["camera_id"],
        "camera_area": camera_area,
        "source_type": event["source_type"],
        "frame_number": frame_number,
        "vehicle_count": len(vehicles),
        "new_track_count": event["new_track_count"],
        "new_crossing_count": event["new_crossing_count"],
        "crossings": event["crossings"],
        "model_name": event["model_name"],
        "model_version": event["model_version"],
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
    camera_id: str = Form("WEB-CAM-001"),
    frame_number: int | None = Form(None),
) -> dict:
    """Analyze a frame directly from web app camera or local stream."""
    return await receive_frame(
        file=file,
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=location_accuracy_m,
        camera_area=camera_area,
        camera_id=camera_id,
        frame_number=frame_number,
    )


@app.get("/api/vehicle-detection-events")
def vehicle_detection_events(limit: int = 100) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    return store.latest_vehicle_events(limit)


@app.get("/api/vehicle-tracks")
def vehicle_tracks(camera_id: str = "", limit: int = 100) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    return store.latest_vehicle_tracks(camera_id.strip(), limit)


@app.get("/api/vehicle-tracks/{track_id}")
def vehicle_track_detail(track_id: str) -> dict:
    result = store.vehicle_track_details(track_id)
    if result is None:
        raise HTTPException(404, "Track not found")
    return result


@app.get("/api/anpr/recognitions")
def plate_recognitions(status: str | None = None, limit: int = 200) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    if status and status.upper() not in {"REVIEW_REQUIRED", "ACCEPTED", "REJECTED"}:
        raise HTTPException(400, "Invalid review status")
    return store.get_plate_recognitions(status=status, limit=limit)


@app.patch("/api/anpr/recognitions/{recognition_id}")
async def review_plate_recognition(recognition_id: str, req: PlateReviewRequest) -> dict:
    status = req.status.strip().upper()
    if status not in {"ACCEPTED", "REJECTED"}:
        raise HTTPException(400, "status must be ACCEPTED or REJECTED")
    corrected = normalize_plate_text(req.corrected_text)
    if status == "ACCEPTED":
        require_vehicle(store, corrected)
    if status == "ACCEPTED" and not is_valid_plate(corrected):
        raise HTTPException(400, "Corrected plate must contain 1-4 letters followed by 1-4 digits")

    existing = store.get_plate_recognition(recognition_id)
    if existing is None:
        raise HTTPException(404, "Plate recognition record not found")
    if existing.get("review_status") != "REVIEW_REQUIRED":
        raise HTTPException(409, "This plate recognition has already been reviewed")

    enforcement_result = None
    if status == "ACCEPTED":
        evidence = store.get_evidence_for_recognition(recognition_id)
        if evidence is None:
            raise HTTPException(409, "Archived evidence for this recognition is unavailable")
        frame_path = settings.snapshots_dir / evidence.get("full_image", "")
        frame = cv2.imread(str(frame_path)) if frame_path.is_file() else None
        if frame is None:
            raise HTTPException(409, "Archived frame is missing or cannot be decoded")
        try:
            observed_at = datetime.fromisoformat(existing["timestamp"])
            bbox = [int(value) for value in existing.get("bbox", "").split(",")]
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(409, "Recognition is missing valid capture time or plate coordinates") from exc
        if len(bbox) != 4:
            raise HTTPException(409, "Recognition is missing valid plate coordinates")

        approved_vehicle = await asyncio.to_thread(store.find_approved_vehicle, corrected)
        latitude = float(evidence["latitude"]) if evidence.get("latitude") else None
        longitude = float(evidence["longitude"]) if evidence.get("longitude") else None
        compliance = await asyncio.to_thread(assess_compliance, approved_vehicle, existing.get("camera_area", ""), observed_at, latitude, longitude)
        plate = {
            "plate_number": corrected,
            "confidence": float(existing.get("confidence") or 0),
            "bbox": bbox,
            "recognition_id": recognition_id,
            "track_id": existing.get("track_id", ""),
        }
        saved, reason = await asyncio.to_thread(
            store.save, frame, plate, latitude, longitude, None,
            evidence.get("vehicle_type") or None, existing.get("camera_area", ""),
            approved_vehicle, compliance, observed_at,
        )

        violation_id = f"VIOL-{recognition_id}" if saved and compliance["status"] == "VIOLATION" else ""
        challan_id = ""
        await asyncio.to_thread(
            store.update_reviewed_evidence,
            recognition_id, corrected,
            approved_vehicle.get("department", "") if approved_vehicle else "",
            evidence.get("vehicle_type", ""), violation_id, challan_id,
        )
        await asyncio.to_thread(store.attach_duty_to_evidence, recognition_id, compliance.get("duty_verification"))
        enforcement_result = {
            "compliance": compliance,
            "saved": saved,
            "reason": reason,
            "violation_id": violation_id,
            "challan_id": challan_id,
            "evidence_id": evidence.get("evidence_id", ""),
        }

    result = store.review_plate_recognition(
        recognition_id, corrected, status, (principal_context.get() or {}).get("sub") or req.reviewer.strip() or "System Administrator", req.notes.strip(),
    )
    if result is None:
        raise HTTPException(404, "Plate recognition record not found")
    return {"success": True, "recognition": result, "enforcement": enforcement_result}


EVIDENCE_REVIEW_STATUSES = {"CAPTURED", "UNDER_REVIEW", "VERIFIED"}
EVIDENCE_CASE_STATUSES = {"UNASSIGNED", "ATTACHED_TO_VIOLATION", "ATTACHED_TO_CHALLAN"}


@app.get("/api/evidence")
def evidence_records(
    query: str | None = None, status: str | None = None, review_status: str | None = None,
    case_status: str | None = None, limit: int = 500,
) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    if status and status.upper() not in EVIDENCE_REVIEW_STATUSES | EVIDENCE_CASE_STATUSES:
        raise HTTPException(400, "Invalid evidence status")
    if review_status and review_status.upper() not in EVIDENCE_REVIEW_STATUSES:
        raise HTTPException(400, "Invalid evidence review status")
    if case_status and case_status.upper() not in EVIDENCE_CASE_STATUSES:
        raise HTTPException(400, "Invalid evidence case status")
    return store.get_evidence_records(
        query=query, status=status, review_status=review_status, case_status=case_status, limit=limit,
    )


@app.get("/api/evidence/{evidence_id}")
def evidence_detail(evidence_id: str) -> dict:
    record = store.get_evidence(evidence_id)
    if record is None:
        raise HTTPException(404, "Evidence record not found")
    return record


@app.post("/api/evidence/{evidence_id}/verify")
def verify_evidence_integrity(evidence_id: str) -> dict:
    result = store.verify_evidence(evidence_id)
    if result is None:
        raise HTTPException(404, "Evidence record not found")
    return result


@app.patch("/api/evidence/{evidence_id}")
def review_evidence_record(evidence_id: str, req: EvidenceReviewRequest) -> dict:
    review_status = req.review_status.strip().upper()
    if review_status not in EVIDENCE_REVIEW_STATUSES - {"CAPTURED"}:
        raise HTTPException(400, "review_status must be UNDER_REVIEW or VERIFIED")
    try:
        result = store.review_evidence(
            evidence_id, review_status, (principal_context.get() or {}).get("sub") or req.reviewer.strip() or "System Administrator", req.notes.strip(),
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if result is None:
        raise HTTPException(404, "Evidence record not found")
    return {"success": True, "evidence": result}


@app.get("/api/evidence/{evidence_id}/download")
def download_evidence_package(evidence_id: str) -> Response:
    record = store.get_evidence(evidence_id)
    if record is None:
        raise HTTPException(404, "Evidence record not found")
    verification = store.verify_evidence(evidence_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = {"evidence": record, "integrity_verification": verification}
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for key in ("full_image", "plate_crop"):
            relative = record.get(key, "")
            path = settings.snapshots_dir / relative if relative else None
            if path and path.exists() and snapshot_allowed(store, relative):
                archive.write(path, arcname=f"images/{path.name}")
    filename = f"Evidence_{evidence_id}.zip"
    return Response(
        content=buffer.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/camera/analyze-video", response_model=VideoAnalysisResponse)
async def analyze_recorded_video(
    file: UploadFile = File(...),
    camera_area: str = Form("Mzd. Division"),
    camera_id: str = Form("VIDEO-CAM-001"),
    sample_every_n_frames: int = Form(15),
    max_analyzed_frames: int = Form(60),
) -> dict:
    """Analyze sampled frames from a recorded video and persist frame-level events."""
    if camera_area not in CAMERA_AREAS:
        raise HTTPException(400, "Select a valid camera area")
    if not 1 <= sample_every_n_frames <= 300 or not 1 <= max_analyzed_frames <= 300:
        raise HTTPException(400, "Invalid video sampling limits")
    suffix = Path(file.filename or "upload.mp4").suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        raise HTTPException(415, "Upload an MP4, AVI, MOV, MKV, or WebM video")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Uploaded video is empty")
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(contents)
            temp_path = temp.name
        capture = cv2.VideoCapture(temp_path)
        if not capture.isOpened():
            raise HTTPException(400, "Could not decode the uploaded video")
        frames_read = 0
        analyzed = 0
        vehicles_detected = 0
        unique_vehicles = 0
        checkpoint_crossings = 0
        stream_id = f"VIDEO-{uuid4().hex}"
        events = []
        while analyzed < max_analyzed_frames:
            ok, frame = capture.read()
            if not ok:
                break
            current_frame = frames_read
            frames_read += 1
            if current_frame % sample_every_n_frames:
                continue
            vehicles, _ = await asyncio.to_thread(detectors.detect, frame)
            height, width = frame.shape[:2]
            event = await asyncio.to_thread(
                store.save_vehicle_event, vehicles, camera_id.strip() or "VIDEO-CAM-001",
                camera_area, "RECORDED_VIDEO", width, height, current_frame,
                stream_id, max(60, sample_every_n_frames * 2),
            )
            events.append({
                "event_id": event["event_id"], "timestamp": event["timestamp"],
                "frame_number": current_frame, "vehicle_count": len(vehicles),
                "new_track_count": event["new_track_count"],
                "new_crossing_count": event["new_crossing_count"],
                "vehicles": event["detections"],
            })
            vehicles_detected += len(vehicles)
            unique_vehicles += event["new_track_count"]
            checkpoint_crossings += event["new_crossing_count"]
            analyzed += 1
        capture.release()
        return {
            "camera_id": camera_id.strip() or "VIDEO-CAM-001", "camera_area": camera_area,
            "filename": file.filename or "uploaded-video", "frames_read": frames_read,
            "frames_analyzed": analyzed, "vehicles_detected": vehicles_detected,
            "unique_vehicles": unique_vehicles, "checkpoint_crossings": checkpoint_crossings,
            "events": events,
        }
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@app.get("/api/live-camera/latest")
def get_latest_live_frame() -> dict:
    """Retrieve the most recent frame processed by any connected scanner."""
    if live_broadcaster.latest_frame:
        return {"active": True, **live_broadcaster.latest_frame}
    return {"active": False, "message": "No live frames captured yet"}


@app.websocket("/ws/live-camera")
async def websocket_live_camera(websocket: WebSocket) -> None:
    """Real-time WebSocket feed streaming live vehicle & plate detections."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    try:
        principal = await asyncio.to_thread(decode_access_token, token, store.engine)
        if principal.get("scope") != "live_feed" or principal["role"] != "Administrator":
            raise HTTPException(401, "Camera-only token cannot access the live feed")
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid or expired access token")
        return
    await live_broadcaster.connect(websocket)
    await asyncio.to_thread(log_access, store.engine, principal["sub"], "LIVE_FEED_OPEN", "/ws/live-camera", 200)
    try:
        while True:
            # Keep socket open and handle ping / messages from web app
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=15)
            except asyncio.TimeoutError:
                await asyncio.to_thread(decode_access_token, token, store.engine)
                continue
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await live_broadcaster.disconnect(websocket)
    except Exception:
        await live_broadcaster.disconnect(websocket)
        await websocket.close(code=1008, reason="Session expired or revoked")


# ==========================================
# VIOLATIONS & E-CHALLAN MANAGEMENT API
# ==========================================
@app.get("/api/violations-summary")
def get_violations_summary(query: str | None = None, stage: str | None = None) -> list[dict]:
    """Return aggregated violations list with warning/challan escalation status."""
    return store.get_violations_summary(query=query, stage=stage)


@app.get("/api/challan/pdf/{plate_number}")
def download_challan_pdf(plate_number: str) -> Response:
    """Compatibility route: return the latest persisted issued document, without writes."""
    challan = store.issued_challan_data(plate_number)
    if not challan:
        raise HTTPException(409, "An approved and issued challan is required")
    cid, pdf_bytes = store.challan_document(challan["case_id"])
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
    challan = store.issued_challan_data(plate_number)
    if not challan:
        raise HTTPException(409, "An approved and issued challan is required")
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
def dispatch_violation_notification(req: ViolationNotificationRequest, request: Request) -> dict:
    reference = req.challan_id
    try:
        # Serialize status transitions with dispatch so an appeal cannot race a send.
        with store._lock:
            result = _dispatch_violation_notification(req)
            if reference:
                sent = any(result.get(key) for key in ("bridge_dispatched", "meta_dispatched", "email_dispatched"))
                store.log_challan_delivery(reference, request.state.principal["sub"], req.channel, "SENT" if sent else "LINK_CREATED")
    except Exception:
        if reference:
            store.log_challan_delivery(reference, request.state.principal["sub"], req.channel, "FAILED_OR_BLOCKED")
        log_access(store.engine, request.state.principal["sub"], "NOTIFICATION", req.plate_number, 400,
                   request.state.principal.get("department_id"), channel=req.channel, outcome="FAILED_OR_BLOCKED")
        raise
    sent = any(result.get(key) for key in ("bridge_dispatched", "meta_dispatched", "email_dispatched"))
    log_access(store.engine, request.state.principal["sub"], "NOTIFICATION", req.plate_number, 200,
               request.state.principal.get("department_id"), channel=req.channel, outcome="SENT" if sent else "LINK_CREATED")
    return result


def _dispatch_violation_notification(req: ViolationNotificationRequest) -> dict:
    """Dispatch official warning or e-challan notice via Local WhatsApp Bridge (Direct PDF/Text), Meta API, or WhatsApp URL."""
    challan_data = store.get_vehicle_challan_data(req.plate_number)
    wants_challan = req.message_type == "challan" or bool(req.challan_id) or (req.violation_count or 0) >= 4
    if wants_challan:
        if not req.challan_id:
            raise HTTPException(409, "Select a specific issued challan before sending")
        challan_data = store.issued_challan_data(req.plate_number, req.challan_id)
        if not challan_data:
            raise HTTPException(409, "Only issued or upheld challans may be sent; pending appeals suspend dispatch")
        req = req.model_copy(update={"message_type": "challan", "violation_count": challan_data["total_violations"],
            "fine_amount": challan_data["fine_amount"], "plate_number": challan_data["plate_number"], "custom_message": ""})
    elif not challan_data or challan_data["total_violations"] >= 4:
        raise HTTPException(409, "Use the challan case workflow for escalated vehicles; a stored warning is required")
    else:
        req = req.model_copy(update={"violation_count": challan_data["total_violations"], "fine_amount": 0})
    history = challan_data.get("violations_history", []) if challan_data else []
    officer = req.officer_name or (challan_data.get("officer_name") if challan_data else "")
    phone = req.recipient_phone or (challan_data.get("officer_phone") if challan_data else "")
    email = req.recipient_email or (challan_data.get("officer_email") if challan_data else "")
    dept = challan_data.get("department", "Government Fleet") if challan_data else "Government Fleet"
    v_count = req.violation_count or (challan_data.get("total_violations", 1) if challan_data else 1)
    fine = req.fine_amount if req.fine_amount is not None else (challan_data.get("fine_amount", 0) if challan_data else 0)
    cid = req.challan_id or (challan_data.get("challan_id") if challan_data else None)

    if (req.message_type == "challan" or v_count >= 4) and not is_challan_stage(challan_data):
        raise HTTPException(409, "Challan available only after escalation")

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
    if wants_challan:
        wa_text = (f"GovTrack / Just Meter issued challan {cid}\nVehicle: {challan_data['plate_number']}\n"
                   f"Department: {dept}\nFine: PKR {fine}\nIssued: {challan_data['issued_at']}\n"
                   f"Due: {challan_data['due_at']}\nPayment collection is not integrated. Contact the reviewing department.")
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
            pdf_bytes = store.challan_document(challan_data["case_id"])[1]
            caption_text = wa_text
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
                pdf_bytes = store.challan_document(challan_data["case_id"])[1]
                caption_text = wa_text
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
            store.challan_document(challan_data["case_id"])[1]
            if (req.message_type == "challan" or v_count >= 4) and challan_data
            else None
        )
        if wants_challan:
            from html import escape
            html = "<p>" + escape(wa_text).replace("\n", "<br>") + "</p>"
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


class RiskPolicyUpdate(BaseModel):
    expected_version: int
    config: RiskPolicyConfig


@app.get("/api/risk/policy")
def get_risk_policy() -> dict:
    return store.get_risk_policy()


@app.put("/api/risk/policy")
def update_risk_policy(payload: RiskPolicyUpdate, request: Request) -> dict:
    try:
        return store.update_risk_policy(payload.config.model_dump(), request.state.principal["sub"], payload.expected_version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/risk/tasks")
def get_risk_tasks(status: str = "OPEN", limit: int = 200) -> list[dict]:
    if status not in {"OPEN", "ACKNOWLEDGED", "ALL"} or not 1 <= limit <= 1000:
        raise HTTPException(400, "Invalid task status or limit")
    return store.get_risk_tasks(None if status == "ALL" else status, limit)


@app.patch("/api/risk/tasks/{task_id}/acknowledge")
def acknowledge_risk_task(task_id: int, request: Request) -> dict:
    principal = request.state.principal
    try:
        task = store.acknowledge_risk_task(task_id, principal["sub"], principal["role"])
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if task is None:
        raise HTTPException(404, "Risk task not found")
    return task
