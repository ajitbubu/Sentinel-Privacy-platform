"""Audit-trail search and export."""
import csv
import io

from sqlalchemy import text
from sqlalchemy.orm import Session

FILTER_SQL = """
    WHERE (:entity_type IS NULL OR a.entity_type = :entity_type)
      AND (:action      IS NULL OR a.action = :action)
      AND (:actor_id    IS NULL OR a.actor_id = :actor_id)
      AND (:entity_id   IS NULL OR a.entity_id = :entity_id)
      AND (:from_date   IS NULL OR a.created_at >= CAST(:from_date AS timestamptz))
      AND (:to_date     IS NULL OR a.created_at <= CAST(:to_date AS timestamptz))
      AND (:gdpr_only = FALSE OR a.is_gdpr_relevant = TRUE)
"""


def _params(**kw):
    return {"entity_type": kw.get("entity_type"), "action": kw.get("action"),
            "actor_id": kw.get("actor_id"), "entity_id": kw.get("entity_id"),
            "from_date": kw.get("from_date"), "to_date": kw.get("to_date"),
            "gdpr_only": kw.get("gdpr_only", False)}


def search(db: Session, limit: int = 100, offset: int = 0, **filters) -> dict:
    params = _params(**filters)
    total = db.execute(text(f"SELECT COUNT(*) FROM audit_log a {FILTER_SQL}"), params).scalar()
    rows = db.execute(
        text(f"""
            SELECT a.id, a.entity_type, a.entity_id, a.action, a.actor_type, a.actor_id,
                   a.actor_ip_address, a.old_values, a.new_values, a.changed_fields,
                   a.reason, a.legal_basis, a.created_at,
                   u.email AS actor_email
            FROM audit_log a
            LEFT JOIN users u ON u.id::text = a.actor_id
            {FILTER_SQL}
            ORDER BY a.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    ).mappings().all()
    return {"entries": [dict(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


def export_csv(db: Session, **filters) -> bytes:
    result = search(db, limit=50_000, **filters)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "created_at", "entity_type", "entity_id", "action", "actor_type",
        "actor_email", "actor_id", "reason", "legal_basis",
    ], extrasaction="ignore")
    writer.writeheader()
    for entry in result["entries"]:
        writer.writerow(entry)
    return buf.getvalue().encode()
