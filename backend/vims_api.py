"""Authenticated VIMS import management; offline JSON is the first adapter."""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .auth import require_roles
from .vims_schema import VimsBatch, VimsImportRequest
from .vims_store import VimsConflict

MAX_IMPORT_BYTES = 5 * 1024 * 1024
SAMPLE_PATH = Path(__file__).parent / "fixtures" / "vims_sample.json"


async def read_contract(request, model):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_IMPORT_BYTES:
            raise HTTPException(413, "Import exceeds the 5 MiB limit")
    try:
        return model.model_validate_json(content)
    except ValidationError as exc:
        raise HTTPException(422, [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                                  for error in exc.errors()]) from exc


def create_vims_router(get_store):
    router = APIRouter(prefix="/api/vims", tags=["VIMS synchronization"])
    admin = require_roles("Administrator")

    @router.get("/schema")
    def schema():
        return VimsBatch.model_json_schema()

    @router.get("/example")
    def example():
        return FileResponse(SAMPLE_PATH, media_type="application/json", filename="vims_sample.json")

    @router.get("/sources")
    def sources():
        return get_store().vims_sources()

    @router.get("/runs")
    def history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        return get_store().vims_history(limit, offset)

    @router.get("/runs/{run_id}")
    def run(run_id: int):
        result = get_store().vims_run(run_id)
        if result is None:
            raise HTTPException(404, "Synchronization run not found")
        return result

    @router.get("/records/{kind}")
    def records(kind: Literal["departments", "vehicles", "drivers", "assignments", "duty_slips"],
                source: str | None = None, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return get_store().vims_records(kind, source, limit, offset)

    @router.post("/preview")
    async def preview(request: Request, principal=Depends(admin)):
        batch = await read_contract(request, VimsBatch)
        try:
            return await run_in_threadpool(get_store().vims_sync, batch, principal["sub"], preview=True)
        except VimsConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/import")
    async def apply_import(request: Request, principal=Depends(admin)):
        body = await read_contract(request, VimsImportRequest)
        try:
            return await run_in_threadpool(get_store().vims_sync, body.batch, principal["sub"], expected_revision=body.expected_revision)
        except VimsConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    return router
