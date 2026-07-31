"""Admin operations on consents with full audit trail."""
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class ConsentAdminService:
    def __init__(self, db: Session):
        self.db = db

    def search(self, subject_email: str | None, status: str | None,
               source: str | None, page: int, limit: int) -> dict:
        where, params = ["c.deleted_at IS NULL"], {
            "limit": min(limit, 200), "offset": (page - 1) * limit
        }
        if subject_email:
            where.append("s.email_normalized = LOWER(TRIM(:email))")
            params["email"] = subject_email
        if status:
            where.append("c.status = :status")
            params["status"] = status
        if source:
            where.append("c.source_system = :source")
            params["source"] = source
        rows = self.db.execute(
            text(f"""
                SELECT c.id, s.email AS subject_email, c.subject_id, p.slug AS purpose,
                       ch.name AS channel, c.status, c.source_system, c.created_at, c.granted_at
                FROM consents c
                JOIN subjects s ON c.subject_id = s.id
                JOIN purposes p ON c.purpose_id = p.id
                JOIN channels ch ON c.channel_id = ch.id
                WHERE {' AND '.join(where)}
                ORDER BY c.created_at DESC LIMIT :limit OFFSET :offset
            """),
            params,
        ).mappings().all()
        return {"consents": [dict(r) for r in rows], "page": page}

    def admin_update(self, consent_id: UUID, status: str, reason: str, actor_id: str) -> dict:
        old = self.db.execute(
            text("SELECT status FROM consents WHERE id = CAST(:cid AS UUID)"), {"cid": str(consent_id)}
        ).mappings().first()
        row = self.db.execute(
            text("""
                UPDATE consents SET status = :status, updated_by_user_id = :actor,
                    granted_at = CASE WHEN :status = 'granted' THEN NOW() ELSE granted_at END,
                    withdrawn_at = CASE WHEN :status = 'withdrawn' THEN NOW() ELSE withdrawn_at END
                WHERE id = CAST(:cid AS UUID) RETURNING id, status
            """),
            {"status": status, "actor": actor_id, "cid": str(consent_id)},
        ).mappings().first()
        self.db.execute(
            text("""
                INSERT INTO audit_log (entity_type, entity_id, action, actor_type, actor_id,
                                       old_values, new_values, reason)
                VALUES ('consent', :eid, 'admin_update', 'user', :actor, :old, :new, :reason)
            """),
            {"eid": str(consent_id), "actor": actor_id,
             "old": json.dumps(dict(old) if old else {}),
             "new": json.dumps({"status": status}), "reason": reason},
        )
        self.db.commit()
        return {**dict(row), "audit_logged": True}
