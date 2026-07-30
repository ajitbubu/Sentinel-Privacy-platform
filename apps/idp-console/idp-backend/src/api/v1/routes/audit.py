"""Immutable audit trail viewer."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db

router = APIRouter()


@router.get("")
def get_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    page: int = 1,
    limit: int = 100,
    user=Depends(require_permission("read:audit")),
    db: Session = Depends(get_db),
):
    where, params = ["1=1"], {"limit": min(limit, 500), "offset": (page - 1) * limit}
    if entity_type:
        where.append("entity_type = :etype")
        params["etype"] = entity_type
    if entity_id:
        where.append("entity_id = :eid")
        params["eid"] = entity_id
    if action:
        where.append("action = :action")
        params["action"] = action
    rows = db.execute(
        text(f"""
            SELECT id, entity_type, entity_id, action, actor_type, actor_id,
                   old_values, new_values, reason, created_at
            FROM audit_log WHERE {' AND '.join(where)}
            ORDER BY created_at DESC LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings().all()
    return {"logs": [dict(r) for r in rows], "page": page}
