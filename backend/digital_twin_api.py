from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import require_roles


def create_digital_twin_router(get_store):
    router = APIRouter(prefix="/api/vehicles", tags=["Vehicle digital twin"], dependencies=[
        Depends(require_roles("Administrator", "Transport Officer", "Supervisory Officer", "Auditor"))])

    def options(as_of: datetime | None = None, start: datetime | None = Query(None, alias="from"),
                end: datetime | None = Query(None, alias="to"),
                history_limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                camera_area: str = Query("", max_length=200)):
        if any(value is not None and value.tzinfo is None for value in (as_of, start, end)):
            raise HTTPException(422, "Dates must include a timezone offset")
        if start and end and start > end:
            raise HTTPException(422, "from must not be later than to")
        return dict(as_of=as_of, start=start, end=end, limit=history_limit, offset=offset, camera_area=camera_area)

    @router.get("/digital-twins")
    def vehicles(query: str = Query("", max_length=100), limit: int = Query(30, ge=1, le=100),
                 offset: int = Query(0, ge=0)):
        return get_store().twin_vehicles(query, limit, offset)

    def profile(vehicle_id, params):
        result = get_store().vehicle_digital_twin(vehicle_id, **params) if vehicle_id is not None else None
        if result is None:
            raise HTTPException(404, "Vehicle not found in the registry")
        return result

    @router.get("/digital-twins/resolve")
    def resolve(plate: str | None = Query(None, max_length=64),
                sighting_key: str | None = Query(None, max_length=200),
                evidence_key: str | None = Query(None, max_length=200)):
        if sum(bool(value) for value in (plate, sighting_key, evidence_key)) != 1:
            raise HTTPException(422, "Provide exactly one vehicle reference")
        vehicle_id = get_store().twin_reference_id(plate=plate, sighting_key=sighting_key, evidence_key=evidence_key)
        if vehicle_id is None:
            raise HTTPException(404, "This record has no linked registry vehicle")
        return {"id": vehicle_id}

    @router.get("/by-plate/{plate}/digital-twin")
    def by_plate(plate: str, params=Depends(options)):
        return profile(get_store().twin_vehicle_id(plate), params)

    @router.get("/{vehicle_id}/digital-twin")
    def by_id(vehicle_id: int, params=Depends(options)):
        return profile(vehicle_id, params)

    return router
