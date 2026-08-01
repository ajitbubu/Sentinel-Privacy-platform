"""Consent endpoints for the authenticated subject."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import get_current_subject
from src.config.database import get_db
from src.repository import consent_repository as repo
from src.services import consent_service
from src.services.consent_service import ConsentError

router = APIRouter()


class GrantRequest(BaseModel):
    purpose: str
    channel: str
    legal_basis: str = "consent"
    metadata: dict = Field(default_factory=dict)
    # Evidence. The notice version is stamped server-side from whatever is
    # published; only the parts the client actually knows are accepted here.
    language_version: str | None = Field(
        default=None, max_length=35,
        description="Language the notice was served in (DPDP s.5(3), Eighth Schedule)")
    capture_mode: str = Field(
        default="digital", pattern="^(digital|physical|thumb_impression_witnessed)$")
    witness_name: str | None = Field(
        default=None, max_length=255,
        description="Required when capture_mode is thumb_impression_witnessed")


class WithdrawRequest(BaseModel):
    reason: str | None = None


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("")
def list_consents(
    status: str | None = Query(None, pattern="^(granted|pending|withdrawn|expired|revoked)$"),
    limit: int = Query(50, le=100, ge=1),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    consents = repo.list_for_subject(db, user["sub"], status, limit, offset)
    return {"consents": consents, "count": len(consents), "limit": limit, "offset": offset}


@router.get("/history")
def consent_history(
    days: int = Query(365, ge=1, le=3650),
    limit: int = Query(200, le=500),
    user: dict = Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    return {"history": repo.history(db, user["sub"], days, limit)}


@router.get("/{consent_id}")
def get_consent(consent_id: str, user: dict = Depends(get_current_subject),
                db: Session = Depends(get_db)):
    consent = repo.get(db, consent_id, user["sub"])
    if consent is None:
        raise HTTPException(404, "Consent not found")
    return consent


@router.post("", status_code=201)
def grant_consent(body: GrantRequest, request: Request,
                  user: dict = Depends(get_current_subject),
                  db: Session = Depends(get_db)):
    try:
        return consent_service.set_consent(
            db, subject_id=user["sub"], purpose_ref=body.purpose,
            channel_ref=body.channel, granted=True, source_system="PMP",
            legal_basis=body.legal_basis, actor_id=user["sub"],
            source_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            metadata=body.metadata,
            language_version=body.language_version,
            capture_mode=body.capture_mode,
            witness_name=body.witness_name,
        )
    except ConsentError as e:
        raise HTTPException(400, str(e))


@router.post("/{consent_id}/withdraw")
def withdraw_consent(consent_id: str, body: WithdrawRequest, request: Request,
                     user: dict = Depends(get_current_subject),
                     db: Session = Depends(get_db)):
    try:
        return consent_service.withdraw(
            db, consent_id=consent_id, subject_id=user["sub"],
            reason=body.reason, actor_id=user["sub"], source_ip=_client_ip(request),
        )
    except ConsentError as e:
        raise HTTPException(400, str(e))
