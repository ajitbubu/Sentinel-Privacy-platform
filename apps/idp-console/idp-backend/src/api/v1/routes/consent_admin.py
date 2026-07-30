"""Admin consent management - DPO can view/override any consent."""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services.consent_admin_service import ConsentAdminService

router = APIRouter()


class AdminConsentUpdate(BaseModel):
    status: str  # granted | withdrawn
    reason: str
    legal_basis: str = "consent"


@router.get("")
def list_consents(
    subject_email: str | None = None,
    status: str | None = None,
    source: str | None = None,
    page: int = 1,
    limit: int = 50,
    user=Depends(require_permission("read:consent_admin")),
    db: Session = Depends(get_db),
):
    return ConsentAdminService(db).search(
        subject_email=subject_email, status=status, source=source, page=page, limit=limit
    )


@router.put("/{consent_id}")
def update_consent(
    consent_id: UUID,
    body: AdminConsentUpdate,
    user=Depends(require_permission("write:consent_admin")),
    db: Session = Depends(get_db),
):
    return ConsentAdminService(db).admin_update(
        consent_id, body.status, body.reason, actor_id=user["sub"]
    )
