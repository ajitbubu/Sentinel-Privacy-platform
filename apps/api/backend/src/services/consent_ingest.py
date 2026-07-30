"""Normalize inbound consent from any source -> shared DB -> real-time events."""
import hashlib
import json

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)


class ConsentIngestService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, data: dict, client_id: str) -> dict:
        email = data["email"].strip().lower()
        subject_id = self._resolve_subject(email, data.get("source"), data.get("source_system_id"))
        status = "granted" if data["consent"] else "withdrawn"
        consent_ids = []
        for purpose in data["purposes"]:
            for channel in data["channels"]:
                row = self.db.execute(
                    text("""
                        INSERT INTO consents (subject_id, purpose_id, channel_id, legal_basis,
                                              status, is_active, granted_at, withdrawn_at,
                                              source_system, created_by_system, metadata)
                        SELECT :sid, p.id, ch.id, :basis, :status, :active,
                               CASE WHEN :status = 'granted' THEN NOW() END,
                               CASE WHEN :status = 'withdrawn' THEN NOW() END,
                               :src, :src, :meta
                        FROM purposes p, channels ch
                        WHERE p.slug = :purpose AND ch.name ILIKE :channel
                        RETURNING id
                    """),
                    {"sid": subject_id, "basis": data["legal_basis"], "status": status,
                     "active": data["consent"], "src": data["source"],
                     "purpose": purpose, "channel": channel,
                     "meta": json.dumps(data.get("metadata", {}))},
                ).mappings().first()
                if row:
                    consent_ids.append(str(row["id"]))
        self.db.commit()
        _redis.publish("channel:consent:updated", json.dumps({
            "subject_id": subject_id, "action": status, "source": data["source"],
        }))
        return {
            "consent_ids": consent_ids, "subject_id": subject_id,
            "sync_status": "queued", "estimated_sync_time": "< 500ms",
        }

    def ingest_bulk(self, consents: list[dict], client_id: str) -> dict:
        batch_key = hashlib.sha256(json.dumps(consents, default=str).encode()).hexdigest()[:16]
        _redis.lpush("queue:bulk_ingest", json.dumps({
            "batch_id": batch_key, "client_id": client_id, "consents": consents,
        }, default=str))
        return {"batch_id": batch_key, "total_records": len(consents), "status": "processing"}

    def ingest_from_salesforce(self, payload: dict) -> None:
        fields = payload.get("fields_changed", {})
        consent = fields.get("Marketing_Consent__c") == "granted" or fields.get("Email_Opt_In__c") is True
        self.ingest({
            "email": payload["email"], "purposes": ["marketing"], "channels": ["Email"],
            "consent": consent, "source": "salesforce",
            "source_system_id": payload.get("contact_id"), "legal_basis": "consent",
            "metadata": {"raw": fields},
        }, client_id="salesforce-webhook")

    def ingest_from_hubspot(self, payload: dict) -> None:
        props = payload.get("properties", {})
        opted_out = props.get("email_open_opt_out", {}).get("value") == "true"
        self.ingest({
            "email": payload["email"], "purposes": ["marketing"], "channels": ["Email"],
            "consent": not opted_out, "source": "hubspot",
            "source_system_id": str(payload.get("object_id")), "legal_basis": "consent",
            "metadata": {"portal_id": payload.get("portal_id")},
        }, client_id="hubspot-webhook")

    def ingest_from_outreach(self, payload: dict) -> None:
        self.ingest({
            "email": payload["email"], "purposes": ["marketing"], "channels": ["Email"],
            "consent": not payload.get("unsubscribed", False), "source": "outreach",
            "source_system_id": str(payload.get("prospect_id")), "legal_basis": "consent",
            "metadata": {},
        }, client_id="outreach-webhook")

    def ingest_from_highspot(self, payload: dict) -> None:
        self.ingest({
            "email": payload["email"], "purposes": ["marketing"], "channels": ["Email"],
            "consent": payload.get("email_opt_in", True), "source": "highspot",
            "source_system_id": str(payload.get("user_id")), "legal_basis": "consent",
            "metadata": {},
        }, client_id="highspot-webhook")

    def _resolve_subject(self, email: str, source: str | None, external_id: str | None) -> str:
        """Identity resolution: find or create subject by normalized email."""
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        row = self.db.execute(
            text("SELECT id FROM subjects WHERE email_normalized = :email AND deleted_at IS NULL"),
            {"email": email},
        ).mappings().first()
        if row:
            if source and external_id:
                col = {"salesforce": "salesforce_id", "hubspot": "hubspot_id",
                       "outreach": "outreach_id", "highspot": "highspot_id"}.get(source)
                if col:
                    self.db.execute(
                        text(f"UPDATE subjects SET {col} = :eid WHERE id = :sid"),
                        {"eid": external_id, "sid": row["id"]},
                    )
            return str(row["id"])
        new_row = self.db.execute(
            text("""
                INSERT INTO subjects (email, email_normalized, email_hash, created_by_system)
                VALUES (:email, :email, :hash, :src)
                RETURNING id
            """),
            {"email": email, "hash": email_hash, "src": source or "API"},
        ).mappings().first()
        return str(new_row["id"])
