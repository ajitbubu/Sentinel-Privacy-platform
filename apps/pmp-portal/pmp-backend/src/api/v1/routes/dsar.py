"""DSAR submission and tracking for the authenticated subject."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import get_current_subject
from src.config.database import get_db
from src.services import dsar_service
from src.services.dsar_service import DSARError

router = APIRouter()


class DSARRequest(BaseModel):
    request_type: str = Field(pattern="^(access|deletion|rectification|export|portability)$")
    description: str | None = Field(default=None, max_length=2000)


@router.post("/request", status_code=201)
def submit(body: DSARRequest, user: dict = Depends(get_current_subject),
           db: Session = Depends(get_db)):
    try:
        return dsar_service.create(
            db, subject_id=user["sub"], request_type=body.request_type,
            description=body.description, actor_id=user["sub"],
        )
    except DSARError as e:
        raise HTTPException(409, str(e))


@router.get("/requests")
def list_requests(user: dict = Depends(get_current_subject), db: Session = Depends(get_db)):
    return {"requests": dsar_service.list_for_subject(db, user["sub"])}


@router.get("/request/{dsar_id}")
def get_request(dsar_id: str, user: dict = Depends(get_current_subject),
                db: Session = Depends(get_db)):
    dsar = dsar_service.get(db, dsar_id, user["sub"])
    if dsar is None:
        raise HTTPException(404, "Request not found")
    return dsar


@router.post("/request/{dsar_id}/cancel")
def cancel_request(dsar_id: str, user: dict = Depends(get_current_subject),
                   db: Session = Depends(get_db)):
    if not dsar_service.cancel(db, dsar_id, user["sub"]):
        raise HTTPException(409, "Request cannot be cancelled at its current stage")
    return {"id": dsar_id, "status": "cancelled"}
