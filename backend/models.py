from typing import Any, Literal

from pydantic import BaseModel, Field


class VehicleDetection(BaseModel):
    label: str
    confidence: float
    bbox: list[int] = Field(description="[x1, y1, x2, y2]")
    track_id: str | None = None


class PlateDetection(BaseModel):
    plate_number: str
    confidence: float
    bbox: list[int]
    saved: bool
    reason: str | None = None
    government_match: dict[str, str] | None = None
    compliance: dict[str, Any] | None = None
    recognition_id: str | None = None
    raw_text: str | None = None
    normalized_text: str | None = None
    suggested_text: str | None = None
    valid_format: bool | None = None
    review_status: str | None = None
    review_reason: str | None = None
    plate_crop: str | None = None
    evidence_id: str | None = None
    track_id: str | None = None


class FrameResponse(BaseModel):
    event_id: str | None = None
    timestamp: str
    camera_id: str = "CAM-001"
    camera_area: str
    source_type: str = "LIVE_FRAME"
    frame_number: int | None = None
    vehicle_count: int = 0
    new_track_count: int = 0
    new_crossing_count: int = 0
    crossings: list[dict] = Field(default_factory=list)
    model_name: str = "yolo11n.pt"
    model_version: str = "YOLO11"
    latitude: float | None = None
    longitude: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    image_data: str | None = None
    vehicles: list[VehicleDetection]
    plates: list[PlateDetection]


class VideoAnalysisResponse(BaseModel):
    source_type: str = "RECORDED_VIDEO"
    camera_id: str
    camera_area: str
    filename: str
    frames_read: int
    frames_analyzed: int
    vehicles_detected: int
    unique_vehicles: int = 0
    checkpoint_crossings: int = 0
    events: list[dict]


class PlateReviewRequest(BaseModel):
    corrected_text: str = ""
    status: str = Field(description="ACCEPTED or REJECTED")
    reviewer: str = "System Administrator"
    notes: str = ""


class EvidenceReviewRequest(BaseModel):
    review_status: str = Field(description="UNDER_REVIEW or VERIFIED")
    reviewer: str = "System Administrator"
    notes: str = ""


class DetectionRecord(BaseModel):
    timestamp: str
    plate_number: str
    confidence: float
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_m: float | None = None
    vehicle_type: str | None = None
    image: str
    bbox: str


class ApprovedVehicleCreate(BaseModel):
    plate_number: str
    vehicle_id: str
    department: str
    authorized_areas: str
    duty_schedule: str = "24/7"
    notes: str = ""
    officer_name: str = ""
    officer_phone: str = ""
    officer_email: str = ""
    risk_context: Literal["", "STANDARD", "SENSITIVE", "CRITICAL"] = ""


class ApprovedVehicleUpdate(BaseModel):
    plate_number: str | None = None
    vehicle_id: str | None = None
    department: str | None = None
    authorized_areas: str | None = None
    duty_schedule: str | None = None
    notes: str | None = None
    officer_name: str | None = None
    officer_phone: str | None = None
    officer_email: str | None = None
    risk_context: Literal["", "STANDARD", "SENSITIVE", "CRITICAL"] | None = None


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: str
    user: dict


class ViolationNotificationRequest(BaseModel):
    plate_number: str
    channel: str = Field("email", description="'email' or 'whatsapp'")
    recipient_email: str | None = None
    recipient_phone: str | None = None
    officer_name: str | None = None
    violation_count: int = 1
    message_type: str = Field("warning", description="'warning' or 'challan'")
    custom_message: str | None = None
    fine_amount: float | None = None
    challan_id: str | None = None


class SMTPConfigRequest(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    user: str = ""
    password: str | None = None
    sender_name: str = "ANPR Fleet Command"
    sender_email: str | None = None
    use_tls: bool = True
    use_ssl: bool = False


class TestEmailRequest(BaseModel):
    recipient_email: str
    config: SMTPConfigRequest | None = None


class MetaWhatsAppConfigRequest(BaseModel):
    phone_number_id: str
    access_token: str | None = None
    api_version: str = "v20.0"


class TestWhatsAppRequest(BaseModel):
    recipient_phone: str
    config: MetaWhatsAppConfigRequest | None = None


