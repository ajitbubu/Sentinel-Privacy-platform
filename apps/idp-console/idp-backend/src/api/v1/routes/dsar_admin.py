"""DSAR admin - DPO processes and fulfills requests."""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services.dsar_admin_service import DSARAdminService

router = APIRouter()


class FulfillRequest(BaseModel):
    format: str = "json"
    include: list[str] = ["consents", "audit_logs", "profile"]
    delivery_method: str = "email"
    notes: str | None = None


class DenyRequest(BaseModel):
    reason: str
    explanation: str


@router.get("")
def list_dsars(
    status: str | None = None,
    user=Depends(require_permission("read:dsar")),
    db: Session = Depends(get_db),
):
    return DSARAdminService(db).list(status=status)


@router.post("/{dsar_id}/fulfill")
def fulfill(
    dsar_id: UUID,
    body: FulfillRequest,
    user=Depends(require_permission("write:dsar")),
    db: Session = Depends(get_db),
):
    return DSARAdminService(db).fulfill(dsar_id, body.model_dump(), actor_id=user["sub"])


@router.post("/{dsar_id}/deny")
def deny(
    dsar_id: UUID,
    body: DenyRequest,
    user=Depends(require_permission("write:dsar")),
    db: Session = Depends(get_db),
):
    return DSARAdminService(db).deny(dsar_id, body.reason, body.explanation, actor_id=user["sub"])
