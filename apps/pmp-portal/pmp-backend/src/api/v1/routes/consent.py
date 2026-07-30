"""User consent management: view, grant, withdraw, history."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import get_current_subject
from src.config.database import get_db
from src.services.consent_service import ConsentService

router = APIRouter()


class GrantConsentRequest(BaseModel):
    purpose: str
    channel: str
    legal_basis: str = "consent"
    metadata: dict = {}


class WithdrawRequest(BaseModel):
    reason: str | None = None


@router.get("")
def list_consents(
    status: str = "granted",
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    return ConsentService(db).list_for_subject(subject["sub"], status=status)


@router.post("", status_code=201)
def grant_consent(
    body: GrantConsentRequest,
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    return ConsentService(db).grant(
        subject_id=subject["sub"],
        purpose=body.purpose,
        channel=body.channel,
        legal_basis=body.legal_basis,
        source_system="PMP",
        metadata=body.metadata,
    )


@router.post("/{consent_id}/withdraw")
def withdraw_consent(
    consent_id: UUID,
    body: WithdrawRequest,
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    result = ConsentService(db).withdraw(
        consent_id=consent_id,
        subject_id=subject["sub"],
        reason=body.reason,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Consent not found")
    return result


@router.get("/history")
def consent_history(
    days: int = 30,
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    return ConsentService(db).history(subject["sub"], days=days)
