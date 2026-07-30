"""DSAR requests - user initiated via PMP."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import get_current_subject
from src.config.database import get_db
from src.services.dsar_service import DSARService

router = APIRouter()

VALID_TYPES = {"access", "deletion", "rectification", "export", "portability"}


class DSARRequest(BaseModel):
    request_type: str
    description: str | None = None
    preferred_format: str = "json"


@router.post("/request", status_code=201)
def submit_dsar(
    body: DSARRequest,
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    if body.request_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"request_type must be one of {VALID_TYPES}")
    return DSARService(db).submit(
        subject_id=subject["sub"],
        request_type=body.request_type,
        description=body.description,
        created_by_system="PMP",
    )


@router.get("/request/{dsar_id}")
def dsar_status(
    dsar_id: UUID,
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    result = DSARService(db).get_for_subject(dsar_id, subject["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="DSAR request not found")
    return result


@router.get("/requests")
def list_dsars(
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    return DSARService(db).list_for_subject(subject["sub"])
