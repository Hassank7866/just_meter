"""Read-only, vehicle-scoped movement trail API."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from .auth import require_roles


class MovementReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str
    notes: str = Field(min_length=10, max_length=2000)


def create_movement_router(get_store):
    router = APIRouter(prefix="/api/vehicles", tags=["Movement intelligence"], dependencies=[
        Depends(require_roles("Administrator", "Transport Officer", "Supervisory Officer", "Auditor"))])

    @router.get("/{vehicle_id}/movement-trail")
    def movement_trail(vehicle_id: int,
                       start: datetime | None = Query(None, alias="from"),
                       end: datetime | None = Query(None, alias="to"),
                       limit: int = Query(30, ge=1, le=100),
                       offset: int = Query(0, ge=0, le=10000)):
        if any(value is not None and value.tzinfo is None for value in (start, end)):
            raise HTTPException(422, "Dates must include a timezone offset")
        if start and end and start > end:
            raise HTTPException(422, "from must not be later than to")
        result = get_store().vehicle_movement_trail(vehicle_id, start=start, end=end,
                                                   limit=limit, offset=offset)
        if result is None:
            raise HTTPException(404, "Vehicle not found in the registry")
        return result

    @router.post("/{vehicle_id}/movement-alerts/{alert_key}/review",
                 dependencies=[Depends(require_roles("Administrator", "Transport Officer", "Supervisory Officer"))])
    def review_alert(vehicle_id: int, alert_key: str, payload: MovementReviewRequest, request: Request):
        try:
            return get_store().review_movement_alert(vehicle_id, alert_key,
                payload.status.upper(), request.state.principal["sub"], payload.notes)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    return router
