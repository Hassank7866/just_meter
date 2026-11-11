"""Administrator checkpoint lines and human-confirmed cross-camera links."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal

from .access import principal_context


class CheckpointInput(BaseModel):
    name: str = Field(default="Checkpoint", min_length=1, max_length=100)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    direction: Literal["BOTH", "A_TO_B", "B_TO_A"] = "BOTH"
    active: bool = True


class LinkConfirmation(BaseModel):
    first_recognition_id: str
    second_recognition_id: str
    max_minutes: int = Field(default=180, ge=1, le=1440)


def create_tracking_router(store_provider):
    router = APIRouter(prefix="/api")

    @router.get("/camera-checkpoints/{camera_id}")
    def get_checkpoint(camera_id: str):
        result = store_provider().get_camera_checkpoint(camera_id.strip())
        if result is None:
            raise HTTPException(404, "Camera checkpoint is not configured")
        return result

    @router.put("/camera-checkpoints/{camera_id}")
    def set_checkpoint(camera_id: str, request: CheckpointInput):
        try:
            return store_provider().save_camera_checkpoint(camera_id.strip(), request.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/checkpoint-crossings")
    def list_crossings(camera_id: str = "", limit: int = Query(default=100, ge=1, le=1000)):
        return store_provider().list_checkpoint_crossings(camera_id.strip(), limit)

    @router.get("/track-links/candidates")
    def link_candidates(max_minutes: int = Query(default=180, ge=1, le=1440),
                        lookback_days: int = Query(default=7, ge=1, le=30),
                        limit: int = Query(default=100, ge=1, le=100)):
        return store_provider().cross_camera_candidates(max_minutes, lookback_days, limit)

    @router.get("/track-links")
    def confirmed_links(limit: int = Query(default=100, ge=1, le=1000)):
        return store_provider().list_cross_camera_links(limit)

    @router.post("/track-links")
    def confirm_link(request: LinkConfirmation):
        actor = (principal_context.get() or {}).get("sub") or "unknown"
        try:
            return store_provider().confirm_cross_camera_link(
                request.first_recognition_id, request.second_recognition_id,
                actor, request.max_minutes)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    return router
