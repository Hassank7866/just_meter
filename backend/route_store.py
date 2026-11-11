"""Administrator-approved route configuration and capture-time lookup."""
from sqlalchemy import or_, select

from .config import get_local_now
from .db_models import ApprovedRoute, Department, Vehicle
from .db_records import normalized
from .route_policy import RouteRequest, route_window


def route_dict(item: ApprovedRoute) -> dict:
    return {key: getattr(item, key) for key in (
        "id", "name", "department_id", "vehicle_id", "valid_from", "valid_until",
        "weekdays", "camera_ids", "camera_areas", "corridor_polygon",
        "require_assignment", "require_duty", "enforce_dates", "active", "revision",
        "approved_by", "approved_at")}


class RouteStore:
    def list_approved_routes(self, include_inactive=True) -> list[dict]:
        with self._lock as session:
            query = select(ApprovedRoute).order_by(ApprovedRoute.id.desc())
            if not include_inactive:
                query = query.where(ApprovedRoute.active.is_(True))
            return [route_dict(item) for item in session.scalars(query)]

    def save_approved_route(self, payload: dict, actor: str, route_id: int | None = None) -> dict:
        values = RouteRequest.model_validate(payload).model_dump()
        with self._lock as session:
            department = session.get(Department, values["department_id"])
            if department is None or not department.active:
                raise LookupError("Active department not found")
            if values["vehicle_id"] is not None:
                vehicle = session.get(Vehicle, values["vehicle_id"])
                if vehicle is None or vehicle.department_id != department.id:
                    raise ValueError("Vehicle must belong to the selected department")
            item = session.get(ApprovedRoute, route_id) if route_id is not None else None
            if route_id is not None and item is None:
                raise LookupError("Approved route not found")
            if item is None:
                item = ApprovedRoute(revision=1, **values, approved_by=actor, approved_at=get_local_now())
                session.add(item)
            else:
                for field, value in values.items():
                    setattr(item, field, value)
                item.revision += 1
                item.approved_by = actor
                item.approved_at = get_local_now()
            session.flush()
            return route_dict(item)

    def route_context_for_plate(self, plate: str, observed_at, duty: dict | None = None) -> dict:
        with self._lock as session:
            vehicle = session.scalar(select(Vehicle).where(Vehicle.normalized_plate == normalized(plate)))
            if vehicle is None or vehicle.department_id is None:
                return route_window([], observed_at, duty)
            routes = session.scalars(select(ApprovedRoute).where(
                ApprovedRoute.department_id == vehicle.department_id,
                or_(ApprovedRoute.vehicle_id == vehicle.id, ApprovedRoute.vehicle_id.is_(None))))
            return route_window([route_dict(item) for item in routes], observed_at, duty) | {
                "vehicle_id": vehicle.id, "department_id": vehicle.department_id}

    def routes_for_vehicle(self, vehicle_id: int, department_id: int) -> list[dict]:
        with self._lock as session:
            routes = session.scalars(select(ApprovedRoute).where(
                ApprovedRoute.department_id == department_id,
                or_(ApprovedRoute.vehicle_id == vehicle_id, ApprovedRoute.vehicle_id.is_(None)),
                ApprovedRoute.active.is_(True)))
            return [route_dict(item) for item in routes]
