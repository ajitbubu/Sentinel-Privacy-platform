"""Admin consent management — cross-system search and DPO override."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services.consent_admin_service import ConsentAdminError, ConsentAdminService

router = APIRouter()


class AdminConsentUpdate(BaseModel):
    status: str = Field(pattern="^(granted|withdrawn)$")
    reason: str = Field(
        min_length=10, max_length=1000,
        description="Recorded permanently and shown in the audit trail. "
                    "Overriding consent without a justification cannot be defended.",
    )


@router.get("")
def search_consents(
    subject_email: str | None = Query(None, description="Prefix match"),
    status: str | None = Query(None, pattern="^(granted|pending|withdrawn|expired|revoked)$"),
    source: str | None = Query(None),
    purpose: str | None = Query(None),
    has_evidence: bool | None = Query(None, description="Filter by whether a notice version was recorded"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("read:consent_admin")),
    db: Session = Depends(get_db),
):
    return ConsentAdminService(db).search(
        subject_email=subject_email, status=status, source=source,
        purpose=purpose, has_evidence=has_evidence, page=page, limit=limit,
    )


@router.get("/{consent_id}")
def consent_timeline(
    consent_id: UUID,
    user=Depends(require_permission("read:consent_admin")),
    db: Session = Depends(get_db),
):
    try:
        return ConsentAdminService(db).timeline(consent_id)
    except ConsentAdminError as e:
        raise HTTPException(404, str(e))


@router.put("/{consent_id}")
def override_consent(
    consent_id: UUID,
    body: AdminConsentUpdate,
    request: Request,
    user=Depends(require_permission("write:consent_admin")),
    db: Session = Depends(get_db),
):
    """Override a consent on a Data Principal's behalf.

    Deliberately bypasses conflict resolution — a DPO acting on a written
    instruction should not be outranked by a CRM — so the audit entry records
    that the bypass happened.
    """
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    try:
        return ConsentAdminService(db).admin_update(
            consent_id, body.status, body.reason, actor_id=user["sub"], actor_ip=ip,
        )
    except ConsentAdminError as e:
        raise HTTPException(400, str(e))
