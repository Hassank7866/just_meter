"""Versioned offline exchange contract; external adapters map to these records."""
from datetime import timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Entity(Contract):
    external_id: Identifier


class DepartmentInput(Entity):
    name: Name
    active: bool = True
    link_existing: bool = False


class VehicleInput(Entity):
    plate_number: Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9 -]+$")]
    vehicle_id: Identifier
    department_external_id: Identifier
    vehicle_type: ShortText = ""
    make: ShortText = ""
    model: ShortText = ""
    color: ShortText = ""
    authorized_areas: list[Name] = Field(min_length=1, max_length=100)
    duty_schedule: Annotated[str, StringConstraints(max_length=100)] = "24/7"
    active: bool = True
    link_existing: bool = False

    @field_validator("plate_number")
    @classmethod
    def plate(cls, value):
        if not any(c.isalnum() for c in value):
            raise ValueError("Plate must contain letters or digits")
        return value.upper()

    @field_validator("duty_schedule")
    @classmethod
    def schedule(cls, value):
        import re
        if value != "24/7" and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Use 24/7 or HH:MM-HH:MM")
        return value


class DriverInput(Entity):
    name: Name
    department_external_id: Identifier
    active: bool = True


class PeriodInput(Entity):
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    status: Literal["ACTIVE", "CANCELLED"] = "ACTIVE"

    @field_validator("valid_from", "valid_until")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def valid_period(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class AssignmentInput(PeriodInput):
    vehicle_external_id: Identifier
    department_external_id: Identifier
    driver_external_id: Identifier
    officer_name: Name


class DutySlipInput(PeriodInput):
    assignment_external_id: Identifier
    destination: Name
    authorized_areas: list[Name] = Field(min_length=1, max_length=100)
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    approved_by: Name


class VimsBatch(Contract):
    schema_version: Literal[1]
    source: Identifier
    batch_id: Identifier
    exported_at: AwareDatetime
    departments: list[DepartmentInput] = Field(default_factory=list, max_length=5000)
    vehicles: list[VehicleInput] = Field(default_factory=list, max_length=5000)
    drivers: list[DriverInput] = Field(default_factory=list, max_length=5000)
    assignments: list[AssignmentInput] = Field(default_factory=list, max_length=5000)
    duty_slips: list[DutySlipInput] = Field(default_factory=list, max_length=5000)

    @field_validator("exported_at")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def unique_records(self):
        count = 0
        for kind in ("departments", "vehicles", "drivers", "assignments", "duty_slips"):
            records = getattr(self, kind)
            count += len(records)
            ids = [record.external_id for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate external_id in {kind}")
        if not 1 <= count <= 5000:
            raise ValueError("A batch must contain between 1 and 5000 records")
        return self


class VimsImportRequest(Contract):
    batch: VimsBatch
    expected_revision: int = Field(ge=0)
