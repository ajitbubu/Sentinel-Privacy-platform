"""Consent business logic - shared DB, publishes real-time events."""
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.event_publisher import publish_event


class ConsentService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_subject(self, subject_id: str, status: str = "granted") -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT c.id, p.slug AS purpose, ch.name AS channel, c.status,
                       c.granted_at, c.withdrawn_at, c.expires_at
                FROM consents c
                JOIN purposes p ON c.purpose_id = p.id
                JOIN channels ch ON c.channel_id = ch.id
                WHERE c.subject_id = :sid AND c.status = :status AND c.deleted_at IS NULL
                ORDER BY c.created_at DESC
            """),
            {"sid": subject_id, "status": status},
        ).mappings().all()
        return [dict(r) for r in rows]

    def grant(self, subject_id: str, purpose: str, channel: str,
              legal_basis: str, source_system: str, metadata: dict) -> dict:
        row = self.db.execute(
            text("""
                INSERT INTO consents (subject_id, purpose_id, channel_id, legal_basis,
                                      status, is_active, granted_at, source_system,
                                      created_by_system, metadata)
                SELECT :sid, p.id, ch.id, :basis, 'granted', TRUE, NOW(), :src, :src, :meta
                FROM purposes p, channels ch
                WHERE p.slug = :purpose AND ch.name = :channel
                RETURNING id, status, granted_at
            """),
            {"sid": subject_id, "basis": legal_basis, "src": source_system,
             "purpose": purpose, "channel": channel, "meta": json.dumps(metadata)},
        ).mappings().first()
        self._audit(subject_id, row["id"], "grant", {"status": "granted"})
        self.db.commit()
        publish_event("consent:updated", {
            "consent_id": str(row["id"]), "subject_id": subject_id,
            "action": "granted", "purpose": purpose, "channel": channel,
        })
        return dict(row)

    def withdraw(self, consent_id: UUID, subject_id: str, reason: str | None) -> dict | None:
        row = self.db.execute(
            text("""
                UPDATE consents
                SET status = 'withdrawn', is_active = FALSE, withdrawn_at = NOW()
                WHERE id = :cid AND subject_id = :sid AND deleted_at IS NULL
                RETURNING id, status, withdrawn_at
            """),
            {"cid": str(consent_id), "sid": subject_id},
        ).mappings().first()
        if not row:
            return None
        self._audit(subject_id, consent_id, "withdraw", {"status": "withdrawn"}, reason)
        self.db.commit()
        publish_event("consent:updated", {
            "consent_id": str(consent_id), "subject_id": subject_id, "action": "withdrawn",
        })
        return dict(row)

    def history(self, subject_id: str, days: int = 30) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT a.id, a.action, a.new_values, a.reason, a.created_at
                FROM audit_log a
                WHERE a.entity_type = 'consent'
                  AND a.entity_id IN (SELECT id FROM consents WHERE subject_id = :sid)
                  AND a.created_at >= NOW() - make_interval(days => :days)
                ORDER BY a.created_at DESC
            """),
            {"sid": subject_id, "days": days},
        ).mappings().all()
        return [dict(r) for r in rows]

    def preference_center(self, subject_id: str) -> dict:
        rows = self.db.execute(
            text("""
                SELECT p.id AS purpose_id, p.name AS purpose, p.is_mandatory,
                       ch.id AS channel_id, ch.name AS channel,
                       COALESCE(c.status, 'not_set') AS consent_status
                FROM purposes p
                CROSS JOIN channels ch
                LEFT JOIN consents c ON c.purpose_id = p.id AND c.channel_id = ch.id
                  AND c.subject_id = :sid AND c.deleted_at IS NULL
                WHERE ch.is_active = TRUE
                ORDER BY p.name, ch.name
            """),
            {"sid": subject_id},
        ).mappings().all()
        return {"preferences": [dict(r) for r in rows]}

    def bulk_update(self, subject_id: str, preferences: list[dict]) -> int:
        count = 0
        for pref in preferences:
            status = "granted" if pref["consent"] else "withdrawn"
            self.db.execute(
                text("""
                    INSERT INTO consents (subject_id, purpose_id, channel_id, legal_basis,
                                          status, is_active, granted_at, withdrawn_at,
                                          source_system, created_by_system)
                    VALUES (:sid, :pid, :chid, 'consent', :status, :active,
                            CASE WHEN :status = 'granted' THEN NOW() END,
                            CASE WHEN :status = 'withdrawn' THEN NOW() END,
                            'PMP', 'PMP')
                """),
                {"sid": subject_id, "pid": pref["purpose_id"], "chid": pref["channel_id"],
                 "status": status, "active": pref["consent"]},
            )
            count += 1
        self.db.commit()
        publish_event("consent:updated", {"subject_id": subject_id, "action": "bulk_update"})
        return count

    def _audit(self, subject_id: str, entity_id, action: str, new_values: dict,
               reason: str | None = None):
        self.db.execute(
            text("""
                INSERT INTO audit_log (entity_type, entity_id, action, actor_type,
                                       actor_id, new_values, reason)
                VALUES ('consent', :eid, :action, 'user', :actor, :new_values, :reason)
            """),
            {"eid": str(entity_id), "action": action, "actor": subject_id,
             "new_values": json.dumps(new_values), "reason": reason},
        )
