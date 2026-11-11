"""Administrator configuration for approved routes."""
from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_roles
from .route_policy import RouteRequest


def create_route_router(get_store):
    router = APIRouter(prefix="/api/approved-routes", tags=["Approved routes"],
                       dependencies=[Depends(require_roles("Administrator"))])

    @router.get("")
    def list_routes():
        return get_store().list_approved_routes()

    def save(payload: RouteRequest, request: Request, route_id: int | None = None):
        try:
            return get_store().save_approved_route(payload.model_dump(),
                                                   request.state.principal["sub"], route_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("", status_code=201)
    def create_route(payload: RouteRequest, request: Request):
        return save(payload, request)

    @router.put("/{route_id}")
    def update_route(route_id: int, payload: RouteRequest, request: Request):
        return save(payload, request, route_id)

    return router
