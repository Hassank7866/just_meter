"""Relational keys and query columns plus capture-time API snapshots.

JSON snapshots preserve legacy fields and historical context; foreign keys and
typed columns establish the relationships used by current processing.
"""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class VimsSource(Base):
    __tablename__ = "vims_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VimsOwned:
    vims_source_id: Mapped[int | None] = mapped_column(ForeignKey("vims_sources.id"))
    vims_external_id: Mapped[str | None] = mapped_column(String(100))
    vims_payload: Mapped[dict | None] = mapped_column(JSON)


class Department(VimsOwned, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("vims_source_id", "vims_external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    record_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Vehicle(VimsOwned, Record, Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("vims_source_id", "vims_external_id"),)
    normalized_plate: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plate_number: Mapped[str] = mapped_column(String(64))
    vehicle_id: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    officer_name: Mapped[str] = mapped_column(String(200), default="")
    officer_email: Mapped[str] = mapped_column(String(254), default="")
    officer_phone: Mapped[str] = mapped_column(String(100), default="")
    authorized_areas: Mapped[list] = mapped_column(JSON, default=list)
    duty_schedule: Mapped[str] = mapped_column(String(100), default="24/7")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class VehicleEvent(Record, Base):
    __tablename__ = "vehicle_events"
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    camera_id: Mapped[str] = mapped_column(String(100))
    vehicle_count: Mapped[int] = mapped_column(Integer)


class VehicleTrack(Base):
    __tablename__ = "vehicle_tracks"
    id: Mapped[int] = mapped_column(primary_key=True)
    track_key: Mapped[str] = mapped_column(String(40), unique=True)
    camera_id: Mapped[str] = mapped_column(String(100), index=True)
    stream_id: Mapped[str] = mapped_column(String(100), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(40))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    first_event_id: Mapped[int] = mapped_column(ForeignKey("vehicle_events.id"))
    last_event_id: Mapped[int] = mapped_column(ForeignKey("vehicle_events.id"))
    last_frame_number: Mapped[int | None] = mapped_column(Integer)
    last_bbox: Mapped[list] = mapped_column(JSON)
    observation_count: Mapped[int] = mapped_column(Integer, default=1)


class TrackObservation(Base):
    __tablename__ = "track_observations"
    __table_args__ = (UniqueConstraint("event_id", "detection_index"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("vehicle_tracks.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("vehicle_events.id"), index=True)
    detection_index: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    frame_number: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[list] = mapped_column(JSON)


class CameraCheckpoint(Base):
    __tablename__ = "camera_checkpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class CheckpointCrossing(Base):
    __tablename__ = "checkpoint_crossings"
    __table_args__ = (UniqueConstraint("checkpoint_id", "revision", "track_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    checkpoint_id: Mapped[int] = mapped_column(ForeignKey("camera_checkpoints.id"), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("vehicle_tracks.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("vehicle_events.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer)
    line_snapshot: Mapped[dict] = mapped_column(JSON)


class Recognition(Record, Base):
    __tablename__ = "plate_recognitions"
    event_id: Mapped[int | None] = mapped_column(ForeignKey("vehicle_events.id"), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    plate_number: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(40), index=True)


class TrackLink(Base):
    __tablename__ = "track_links"
    __table_args__ = (UniqueConstraint("first_track_id", "second_track_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    first_track_id: Mapped[int] = mapped_column(ForeignKey("vehicle_tracks.id"), index=True)
    second_track_id: Mapped[int] = mapped_column(ForeignKey("vehicle_tracks.id"), index=True)
    first_recognition_id: Mapped[int] = mapped_column(ForeignKey("plate_recognitions.id"))
    second_recognition_id: Mapped[int] = mapped_column(ForeignKey("plate_recognitions.id"))
    normalized_plate: Mapped[str] = mapped_column(String(64), index=True)
    elapsed_seconds: Mapped[int] = mapped_column(Integer)
    confirmed_by: Mapped[str] = mapped_column(String(254))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Detection(Record, Base):
    __tablename__ = "detections"
    recognition_id: Mapped[int | None] = mapped_column(ForeignKey("plate_recognitions.id"), unique=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    normalized_plate: Mapped[str] = mapped_column(String(64), index=True)


class Sighting(Record, Base):
    __tablename__ = "government_sightings"
    detection_id: Mapped[int | None] = mapped_column(ForeignKey("detections.id"), unique=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    normalized_plate: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    violation_id: Mapped[str | None] = mapped_column(String(200), unique=True)


class Evidence(Record, Base):
    __tablename__ = "evidence"
    event_id: Mapped[int | None] = mapped_column(ForeignKey("vehicle_events.id"), index=True)
    recognition_id: Mapped[int | None] = mapped_column(ForeignKey("plate_recognitions.id"), index=True)
    sighting_id: Mapped[int | None] = mapped_column(ForeignKey("government_sightings.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    review_status: Mapped[str] = mapped_column(String(40))
    case_status: Mapped[str] = mapped_column(String(40))
    full_image: Mapped[str] = mapped_column(Text)
    full_image_sha256: Mapped[str] = mapped_column(String(64))


class VehicleVerification(Base):
    __tablename__ = "vehicle_verifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    sighting_id: Mapped[int] = mapped_column(ForeignKey("government_sightings.id"), unique=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expected: Mapped[dict] = mapped_column(JSON)
    observed: Mapped[dict] = mapped_column(JSON)
    comparisons: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), index=True)
    risk_status: Mapped[str] = mapped_column(String(40), default="NONE")
    reviewed_by: Mapped[str | None] = mapped_column(String(254))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str] = mapped_column(Text, default="")


class Geofence(Record, Base):
    __tablename__ = "geofences"
    name: Mapped[str] = mapped_column(String(200))


class ApprovedRoute(Base):
    __tablename__ = "approved_routes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    weekdays: Mapped[list] = mapped_column(JSON)
    camera_ids: Mapped[list] = mapped_column(JSON)
    camera_areas: Mapped[list] = mapped_column(JSON)
    corridor_polygon: Mapped[list] = mapped_column(JSON)
    require_assignment: Mapped[bool] = mapped_column(Boolean, default=False)
    require_duty: Mapped[bool] = mapped_column(Boolean, default=False)
    enforce_dates: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    approved_by: Mapped[str] = mapped_column(String(254))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MovementAlertReview(Base):
    __tablename__ = "movement_alert_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_key: Mapped[str] = mapped_column(String(160), unique=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("approved_routes.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    reviewed_by: Mapped[str] = mapped_column(String(254))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text)


class RiskPolicy(Base):
    __tablename__ = "risk_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(254))
    config: Mapped[dict] = mapped_column(JSON)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (CheckConstraint("score >= 0 AND score <= 100", name="risk_score_range"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sighting_id: Mapped[int] = mapped_column(ForeignKey("government_sightings.id"), unique=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("risk_policies.id"))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(40), index=True)
    result: Mapped[dict] = mapped_column(JSON)


class RiskTask(Base):
    __tablename__ = "risk_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id"), unique=True)
    priority: Mapped[str] = mapped_column(String(30), index=True)
    assigned_role: Mapped[str] = mapped_column(String(40))
    recommended_action: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    acknowledged_by: Mapped[str | None] = mapped_column(String(254))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSON)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)


class ImportBatch(Base):
    __tablename__ = "legacy_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(200), unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Driver(VimsOwned, Base):
    __tablename__ = "drivers"
    __table_args__ = (UniqueConstraint("vims_source_id", "vims_external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    active: Mapped[bool] = mapped_column(Boolean)


class VehicleAssignment(VimsOwned, Base):
    __tablename__ = "vehicle_assignments"
    __table_args__ = (
        UniqueConstraint("vims_source_id", "vims_external_id"),
        CheckConstraint("valid_until > valid_from", name="assignment_period"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    officer_name: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))


class DutySlip(VimsOwned, Base):
    __tablename__ = "duty_slips"
    __table_args__ = (
        UniqueConstraint("vims_source_id", "vims_external_id"),
        CheckConstraint("valid_until > valid_from", name="duty_period"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("vehicle_assignments.id"), index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    destination: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(1000))
    authorized_areas: Mapped[list] = mapped_column(JSON)
    approved_by: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))


class VimsSyncRun(Base):
    __tablename__ = "vims_sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("vims_sources.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(100), index=True)
    checksum: Mapped[str] = mapped_column(String(64))
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(30))
    summary: Mapped[dict] = mapped_column(JSON)
    changes: Mapped[list] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class DutyCoverage(Base):
    __tablename__ = "duty_coverage"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("vims_sources.id"), unique=True)
    source_revision: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_age_hours: Mapped[int] = mapped_column(Integer)
    confirmed_by: Mapped[str] = mapped_column(String(254))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DutyReview(Base):
    __tablename__ = "duty_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    sighting_id: Mapped[int] = mapped_column(ForeignKey("government_sightings.id"), unique=True)
    reviewed_by: Mapped[str] = mapped_column(String(254))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text)
    original: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[dict] = mapped_column(JSON)


class Challan(Base):
    __tablename__ = "challans"
    __table_args__ = (CheckConstraint("fine_amount >= 0", name="challan_fine_nonnegative"),
                     CheckConstraint("version >= 1", name="challan_version_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(80), unique=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    sighting_id: Mapped[int] = mapped_column(ForeignKey("government_sightings.id"), unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    fine_amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(254))
    approved_by: Mapped[str | None] = mapped_column(String(254))
    prepared_by: Mapped[str] = mapped_column(String(254))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[str | None] = mapped_column(String(254))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    document: Mapped[bytes | None] = mapped_column(LargeBinary)
    document_sha256: Mapped[str | None] = mapped_column(String(64))


class ChallanEvent(Base):
    __tablename__ = "challan_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    challan_id: Mapped[int] = mapped_column(ForeignKey("challans.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
