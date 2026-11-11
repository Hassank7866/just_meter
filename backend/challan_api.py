from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from .auth import require_principal, require_roles
from .challan_store import STATES


class DraftRequest(BaseModel):
    vehicle_id: int = Field(gt=0)


class ChallanActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["approve", "reject", "issue", "appeal", "uphold", "cancel", "amend", "reopen"]
    expected_version: int = Field(ge=1)
    notes: str = Field(min_length=10, max_length=2000)
    fine_amount: int | None = Field(None, ge=0, le=1000000)
    review_fingerprint: str | None = Field(None, min_length=64, max_length=64)


def create_challan_router(get_store):
    router = APIRouter(prefix="/api/challans", tags=["Digital challan"], dependencies=[Depends(require_principal)])

    def call(operation, *args):
        try:
            return operation(*args)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("")
    def listing(status: str | None = None, vehicle_id: int | None = Query(None, gt=0),
                limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
        if status and status not in STATES:
            raise HTTPException(422, "Unknown challan status")
        return get_store().list_challans(status, vehicle_id, limit, offset)

    @router.post("")
    def create(body: DraftRequest, principal=Depends(require_roles("Administrator", "Transport Officer", "Supervisory Officer"))):
        return call(get_store().create_challan_draft, body.vehicle_id, principal["sub"])

    @router.get("/{case_id}")
    def detail(case_id: int):
        result = get_store().challan_detail(case_id)
        if result is None:
            raise HTTPException(404, "Challan not found")
        return result

    @router.post("/{case_id}/actions")
    def action(case_id: int, body: ChallanActionRequest, principal=Depends(require_principal)):
        return call(get_store().challan_action, case_id, body, principal)

    @router.get("/{case_id}/pdf")
    def document(case_id: int):
        reference, data = call(get_store().challan_document, case_id)
        return Response(data, media_type="application/pdf", headers={
            "Content-Disposition": f'inline; filename="{reference}.pdf"', "Cache-Control": "private, no-store"})

    return router
