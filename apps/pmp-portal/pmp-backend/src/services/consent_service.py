"""Consent business logic, including conflict resolution.

CONFLICT RULE (see Build-Plan decision note)
--------------------------------------------
Naive "opt-out always wins" permanently breaks re-subscription: a person who
withdraws could never opt back in, because their new grant would always lose to
the older withdrawal. The implemented rule is:

  1. Inside the conflict window (default 24h), a withdrawal beats a grant
     regardless of timestamp. This is what stops a stale CRM sync from
     resurrecting consent someone just withdrew.
  2. Outside the window, source tier decides: a first-party explicit action
     (PMP portal, cookie banner) beats a third-party sync (Salesforce, HubSpot).
  3. Among same-tier signals, newest timestamp wins.

Mandatory purposes cannot be withdrawn; that is enforced here, not in the UI,
because the UI is not a security boundary.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.repository import consent_repository as repo
from src.services import event_publisher
from src.services.audit_service import log_audit

CONFLICT_WINDOW_HOURS = 24

# Higher tier wins outside the conflict window.
SOURCE_TIER = {
    "PMP": 3, "pmp_portal": 3, "cookie_banner": 3, "IDP": 3,   # first-party explicit
    "API": 2,                                                   # direct API
    "salesforce": 1, "hubspot": 1, "outreach": 1, "highspot": 1,  # third-party sync
}
DEFAULT_TIER = 1


class ConsentError(Exception):
    """Business-rule violation; message is safe to surface to the caller."""


def _tier(source: str) -> int:
    return SOURCE_TIER.get(source, SOURCE_TIER.get(source.lower(), DEFAULT_TIER))


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def should_apply(existing: dict | None, new_status: str, new_source: str,
                 now: datetime | None = None) -> tuple[bool, str]:
    """Decide whether an incoming signal supersedes the existing consent.

    Returns (apply, reason). Pure function — unit-testable without a database.
    """
    if existing is None:
        return True, "no prior consent"

    now = now or datetime.now(timezone.utc)
    if existing["status"] == new_status:
        return False, "no change"

    withdrawn_at = _aware(existing.get("withdrawn_at"))
    if existing["status"] == "withdrawn" and new_status == "granted" and withdrawn_at:
        if now - withdrawn_at < timedelta(hours=CONFLICT_WINDOW_HOURS):
            # Rule 1 — protect a fresh withdrawal from stale grants.
            if _tier(new_source) < 3:
                return False, (
                    f"withdrawal within {CONFLICT_WINDOW_HOURS}h conflict window "
                    f"outranks grant from '{new_source}'"
                )
            # A first-party explicit re-grant is a real human decision; honour it.
            return True, "first-party explicit re-grant inside window"

    # Rule 2 — tier precedence outside the window.
    existing_tier = _tier(existing.get("source_system", ""))
    if _tier(new_source) < existing_tier:
        return False, (
            f"source '{new_source}' outranked by existing '{existing.get('source_system')}'"
        )

    # Rule 3 — same or higher tier, newest wins (we are the newest by construction).
    return True, "supersedes prior consent"


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
