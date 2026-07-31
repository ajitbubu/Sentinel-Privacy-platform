"""DSAR queue and fulfilment (DPO only)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services import dsar_admin_service
from src.services.dsar_admin_service import DSARAdminError

router = APIRouter()


@router.get("")
def dsar_queue(status: str | None = Query(None), limit: int = Query(50, le=200),
               db: Session = Depends(get_db),
               user: dict = Depends(require_permission("read:dsar"))):
    requests = dsar_admin_service.queue(db, status, limit)
    return {
        "requests": requests,
        "overdue": sum(1 for r in requests if r["is_overdue"]),
        "due_soon": sum(1 for r in requests
                        if not r["is_overdue"] and (r["days_remaining"] or 99) <= 5),
    }


@router.get("/{dsar_id}/preview")
def preview_export(dsar_id: str, db: Session = Depends(get_db),
                   user: dict = Depends(require_permission("read:dsar"))):
    """What would be sent, without marking the request fulfilled."""
    from sqlalchemy import text
    subject_id = db.execute(
        text("SELECT subject_id FROM dsar_requests WHERE id = :did"), {"did": dsar_id}
    ).scalar()
    if subject_id is None:
        raise HTTPException(404, "Request not found")
    try:
        return dsar_admin_service.collect_subject_data(db, str(subject_id))
    except DSARAdminError as e:
        raise HTTPException(404, str(e))


@router.post("/{dsar_id}/fulfil")
def fulfil(dsar_id: str, format: str = Query("json", pattern="^(json|csv|pdf)$"),
           db: Session = Depends(get_db),
           user: dict = Depends(require_permission("write:dsar"))):
    try:
        content, media, filename = dsar_admin_service.fulfil(db, dsar_id, user["sub"], format)
    except DSARAdminError as e:
        raise HTTPException(400, str(e))
    return Response(
        content=content, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class DenyRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000,
                        description="Shown to the data subject — must be specific")


@router.post("/{dsar_id}/deny")
def deny(dsar_id: str, body: DenyRequest, db: Session = Depends(get_db),
         user: dict = Depends(require_permission("write:dsar"))):
    try:
        return dsar_admin_service.deny(db, dsar_id, user["sub"], body.reason)
    except DSARAdminError as e:
        raise HTTPException(400, str(e))
