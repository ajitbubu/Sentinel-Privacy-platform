"""DSAR fulfillment automation for DPO."""
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class DSARAdminService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, status: str | None = None) -> dict:
        q = """
            SELECT d.id, s.email AS subject_email, d.request_type, d.status,
                   d.submitted_at, d.due_date,
                   EXTRACT(DAY FROM d.due_date - NOW())::int AS days_remaining
            FROM dsar_requests d JOIN subjects s ON d.subject_id = s.id
        """
        params = {}
        if status:
            q += " WHERE d.status = :status"
            params["status"] = status
        rows = self.db.execute(text(q + " ORDER BY d.due_date ASC"), params).mappings().all()
        return {"requests": [dict(r) for r in rows]}

    def fulfill(self, dsar_id: UUID, options: dict, actor_id: str) -> dict:
        # Gather subject data (consents, audit, profile) -> export file -> notify subject
        row = self.db.execute(
            text("""
                UPDATE dsar_requests
                SET status = 'fulfilled', fulfilled_at = NOW(), processed_by_user_id = :actor
                WHERE id = :did RETURNING id, status, fulfilled_at
            """),
            {"did": str(dsar_id), "actor": actor_id},
        ).mappings().first()
        self._audit(dsar_id, "fulfill", actor_id, options.get("notes"))
        self.db.commit()
        return {**dict(row), "message": "DSAR fulfilled; subject notified with download link"}

    def deny(self, dsar_id: UUID, reason: str, explanation: str, actor_id: str) -> dict:
        row = self.db.execute(
            text("""
                UPDATE dsar_requests
                SET status = 'denied', denial_reason = :reason, processed_by_user_id = :actor
                WHERE id = :did RETURNING id, status
            """),
            {"did": str(dsar_id), "reason": f"{reason}: {explanation}", "actor": actor_id},
        ).mappings().first()
        self._audit(dsar_id, "deny", actor_id, explanation)
        self.db.commit()
        return dict(row)

    def _audit(self, dsar_id, action: str, actor_id: str, reason: str | None):
        self.db.execute(
            text("""
                INSERT INTO audit_log (entity_type, entity_id, action, actor_type, actor_id, reason)
                VALUES ('dsar', :eid, :action, 'user', :actor, :reason)
            """),
            {"eid": str(dsar_id), "action": action, "actor": actor_id, "reason": reason},
        )
