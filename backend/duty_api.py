from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import require_roles
from .duty_verification import CoverageRequest, DutyReviewRequest
from .access import require_vehicle


def create_duty_router(get_store):
    router = APIRouter(prefix="/api/duty", tags=["Duty verification"])

    @router.get("/coverage")
    def coverage():
        return get_store().duty_coverage()

    @router.put("/coverage/{source}")
    def confirm(source: str, body: CoverageRequest, principal=Depends(require_roles("Administrator"))):
        try:
            return get_store().confirm_duty_coverage(source, body, principal["sub"])
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/check")
    def check(plate: str = Query(min_length=1, max_length=64),
              observed_at: datetime = Query(), camera_area: str = Query(min_length=1, max_length=200)):
        if observed_at.tzinfo is None:
            raise HTTPException(422, "observed_at must include a timezone offset")
        require_vehicle(get_store(), plate)
        return get_store().verify_vehicle_duty(plate, observed_at, camera_area)

    @router.get("/observations")
    def observations(pending: bool = True, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return get_store().duty_observations(pending, limit, offset)

    @router.get("/observations/{sighting_id}")
    def observation(sighting_id: int):
        result = get_store().duty_observation(sighting_id)
        if result is None:
            raise HTTPException(404, "Observation not found")
        return result

    @router.post("/observations/{sighting_id}/review")
    def review(sighting_id: int, body: DutyReviewRequest,
               principal=Depends(require_roles("Administrator", "Supervisory Officer"))):
        try:
            return get_store().review_vehicle_duty(sighting_id, body, principal["sub"])
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    return router
