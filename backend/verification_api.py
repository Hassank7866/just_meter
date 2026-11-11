"""Vehicle verification review and confirmed mismatch risk queue."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .auth import require_roles


class VerificationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: str
    make: str = Field(default="", max_length=100)
    model: str = Field(default="", max_length=100)
    color: str = Field(default="", max_length=100)
    notes: str = Field(min_length=10, max_length=2000)


def create_verification_router(get_store):
    router = APIRouter(prefix="/api", tags=["Vehicle verification"], dependencies=[
        Depends(require_roles("Administrator", "Transport Officer", "Supervisory Officer", "Auditor"))])

    @router.get("/vehicles/{vehicle_id}/verifications")
    def list_verifications(vehicle_id: int, limit: int = 100):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "limit must be between 1 and 100")
        result = get_store().list_vehicle_verifications(vehicle_id, limit)
        if result is None:
            raise HTTPException(404, "Vehicle not found")
        return result

    @router.post("/vehicles/{vehicle_id}/verifications/{verification_id}/review",
                 dependencies=[Depends(require_roles("Administrator", "Transport Officer", "Supervisory Officer"))])
    def review(vehicle_id: int, verification_id: int, payload: VerificationReviewRequest, request: Request):
        try:
            return get_store().review_vehicle_verification(vehicle_id, verification_id,
                {"make": payload.make, "model": payload.model, "color": payload.color},
                payload.decision.upper(), payload.notes, request.state.principal["sub"])
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/vehicle-verification/risk-queue")
    def risk_queue(limit: int = 100):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "limit must be between 1 and 100")
        return get_store().vehicle_verification_risk_queue(limit)

    return router
