from pydantic import BaseModel, Field


class VehicleDetection(BaseModel):
    label: str
    confidence: float
    bbox: list[int] = Field(description="[x1, y1, x2, y2]")


class PlateDetection(BaseModel):
    plate_number: str
    confidence: float
    bbox: list[int]
    saved: bool
    reason: str | None = None
    government_match: dict[str, str] | None = None
    compliance: dict[str, str] | None = None


class FrameResponse(BaseModel):
    timestamp: str
    camera_area: str
    latitude: float | None = None
    longitude: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    image_data: str | None = None
    vehicles: list[VehicleDetection]
    plates: list[PlateDetection]


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



