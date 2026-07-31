"""Consent business logic.

Conflict resolution lives in `consent_rules` — a dependency-free module — so
the rules can be unit-tested without a database. This module handles the I/O:
validation, persistence, audit, and event publication.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.repository import consent_repository as repo
from src.services import event_publisher
from src.services.audit_service import log_audit
from src.services.consent_rules import CONFLICT_WINDOW_HOURS, should_apply, tier  # noqa: F401


class ConsentError(Exception):
    """Business-rule violation; message is safe to surface to the caller."""


def _expiry_for(purpose: dict) -> datetime | None:
    days = purpose.get("retention_period_days")
    return datetime.now(timezone.utc) + timedelta(days=days) if days else None


def set_consent(db: Session, *, subject_id: str, purpose_ref: str, channel_ref: str,
                granted: bool, source_system: str = "PMP", legal_basis: str = "consent",
                actor_id: str | None = None, source_ip: str | None = None,
                user_agent: str | None = None, reason: str | None = None,
                metadata: dict | None = None) -> dict:
    """Grant or withdraw consent. Idempotent, audited, and event-publishing."""
    purpose = repo.resolve_purpose(db, purpose_ref)
    if purpose is None:
        raise ConsentError(f"Unknown purpose: {purpose_ref}")
    channel = repo.resolve_channel(db, channel_ref)
    if channel is None:
        raise ConsentError(f"Unknown channel: {channel_ref}")

    if purpose["is_mandatory"] and not granted:
        raise ConsentError(
            f"'{purpose['name']}' is strictly necessary and cannot be withdrawn."
        )

    allowed = purpose.get("legal_basis_allowed") or []
    if allowed and legal_basis not in allowed:
        raise ConsentError(
            f"Legal basis '{legal_basis}' not permitted for purpose '{purpose['name']}'."
        )

    new_status = "granted" if granted else "withdrawn"
    existing = repo.find_active(db, subject_id, str(purpose["id"]), str(channel["id"]))

    apply, decision = should_apply(existing, new_status, source_system)
    if not apply:
        return {
            "applied": False, "reason": decision,
            "consent_id": str(existing["id"]) if existing else None,
            "status": existing["status"] if existing else None,
        }

    old_values = {"status": existing["status"]} if existing else {}

    if existing:
        updated = repo.update_status(db, str(existing["id"]), new_status)
        consent_id = str(updated["id"])
    else:
        consent_id = repo.insert(
            db, subject_id=subject_id, purpose_id=str(purpose["id"]),
            channel_id=str(channel["id"]), status=new_status, legal_basis=legal_basis,
            source_system=source_system, source_ip=source_ip, user_agent=user_agent,
            expires_at=_expiry_for(purpose) if granted else None, metadata=metadata,
        )
    db.commit()

    log_audit(
        db, entity_type="consent", entity_id=consent_id,
        action="granted" if granted else "withdrawn",
        actor_id=actor_id or subject_id,
        actor_type="user" if source_system in ("PMP", "pmp_portal") else "system",
        actor_ip=source_ip, old_values=old_values,
        new_values={"status": new_status, "purpose": purpose["name"],
                    "channel": channel["name"], "source": source_system},
        reason=reason, legal_basis=legal_basis,
    )

    event_publisher.publish("consent.updated", {
        "consent_id": consent_id, "subject_id": subject_id,
        "purpose": purpose["name"], "purpose_slug": purpose["slug"],
        "channel": channel["name"], "status": new_status, "source": source_system,
    })

    return {
        "applied": True, "reason": decision, "consent_id": consent_id,
        "status": new_status, "purpose": purpose["name"], "channel": channel["name"],
    }


def set_many(db: Session, *, subject_id: str, preferences: list[dict], **kwargs) -> dict:
    """Bulk preference update. Partial failures are reported, not fatal."""
    applied, skipped, errors = [], [], []
    for pref in preferences:
        try:
            result = set_consent(
                db, subject_id=subject_id,
                purpose_ref=pref["purpose"], channel_ref=pref["channel"],
                granted=bool(pref["granted"]), **kwargs,
            )
            (applied if result["applied"] else skipped).append(result)
        except ConsentError as e:
            errors.append({"purpose": pref.get("purpose"), "channel": pref.get("channel"),
                           "error": str(e)})
    return {"applied": len(applied), "skipped": len(skipped), "errors": errors,
            "details": applied + skipped}


def withdraw(db: Session, *, consent_id: str, subject_id: str, reason: str | None = None,
             source_system: str = "PMP", actor_id: str | None = None,
             source_ip: str | None = None) -> dict:
    existing = repo.get(db, consent_id, subject_id)
    if existing is None:
        raise ConsentError("Consent not found")
    return set_consent(
        db, subject_id=subject_id,
        purpose_ref=str(existing["purpose_id"]), channel_ref=str(existing["channel_id"]),
        granted=False, source_system=source_system, actor_id=actor_id,
        source_ip=source_ip, reason=reason,
    )
