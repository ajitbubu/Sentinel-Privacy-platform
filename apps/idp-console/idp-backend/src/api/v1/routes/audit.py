"""Audit-trail search and export."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services import audit_query_service

router = APIRouter()


def _validate_uuid(value: str | None, field: str) -> str | None:
    """Reject malformed UUIDs at the edge with a 400.

    The SQL casts the bind parameter to UUID so the index stays usable; without
    this guard a typo in the filter box surfaces as an opaque 500.
    """
    if value in (None, ""):
        return None
    try:
        _uuid.UUID(value)
    except ValueError:
        raise HTTPException(400, f"{field} must be a valid UUID")
    return value


def _filters(entity_type: str | None, action: str | None, actor_id: str | None,
             entity_id: str | None, from_date: str | None, to_date: str | None,
             gdpr_only: bool) -> dict:
    return {"entity_type": entity_type, "action": action, "actor_id": actor_id,
            "entity_id": _validate_uuid(entity_id, "entity_id"),
            "from_date": from_date, "to_date": to_date,
            "gdpr_only": gdpr_only}


@router.get("")
def search_audit(
    entity_type: str | None = Query(None), action: str | None = Query(None),
    actor_id: str | None = Query(None), entity_id: str | None = Query(None),
    from_date: str | None = Query(None), to_date: str | None = Query(None),
    gdpr_only: bool = Query(False),
    limit: int = Query(100, le=500), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("read:audit")),
):
    return audit_query_service.search(
        db, limit=limit, offset=offset,
        **_filters(entity_type, action, actor_id, entity_id, from_date, to_date, gdpr_only),
    )


@router.get("/export")
def export_audit(
    entity_type: str | None = Query(None), action: str | None = Query(None),
    actor_id: str | None = Query(None), entity_id: str | None = Query(None),
    from_date: str | None = Query(None), to_date: str | None = Query(None),
    gdpr_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("read:audit")),
):
    csv_bytes = audit_query_service.export_csv(
        db, **_filters(entity_type, action, actor_id, entity_id, from_date, to_date, gdpr_only)
    )
    return Response(content=csv_bytes, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="audit-trail.csv"'})
