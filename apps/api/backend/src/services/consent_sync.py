"""Apply a canonical ConsentSignal, honouring the conflict rules.

The precedence logic is deliberately identical to the PMP service — duplicated
as a small pure function rather than shared through a package, because these
are separately deployable services. The invariant is covered by tests on both
sides; if they ever diverge, the tests fail.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.integrations import ConsentSignal

CONFLICT_WINDOW_HOURS = 24
SOURCE_TIER = {"PMP": 3, "pmp_portal": 3, "cookie_banner": 3, "IDP": 3, "API": 2}
DEFAULT_TIER = 1


def _tier(source: str) -> int:
    return SOURCE_TIER.get(source, DEFAULT_TIER)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def should_apply(existing: dict | None, new_status: str, new_source: str,
                 now: datetime | None = None) -> tuple[bool, str]:
    if existing is None:
        return True, "no prior consent"
    now = now or datetime.now(timezone.utc)
    if existing["status"] == new_status:
        return False, "no change"

    withdrawn_at = _aware(existing.get("withdrawn_at"))
    if existing["status"] == "withdrawn" and new_status == "granted" and withdrawn_at:
        if now - withdrawn_at < timedelta(hours=CONFLICT_WINDOW_HOURS):
            if _tier(new_source) < 3:
                return False, f"withdrawal within {CONFLICT_WINDOW_HOURS}h outranks '{new_source}'"
            return True, "first-party explicit re-grant inside window"

    if _tier(new_source) < _tier(existing.get("source_system", "")):
        return False, f"'{new_source}' outranked by '{existing.get('source_system')}'"
    return True, "supersedes prior consent"


def apply(db: Session, *, subject_id: str, signal: ConsentSignal) -> dict:
    purpose_id = db.execute(
        text("SELECT id FROM purposes WHERE slug = :s"), {"s": signal.purpose}
    ).scalar()
    channel_id = db.execute(
        text("SELECT id FROM channels WHERE type = :t OR lower(name) = :t"),
        {"t": signal.channel},
    ).scalar()
    if not purpose_id or not channel_id:
        return {"applied": False, "reason": f"unknown purpose/channel "
                                            f"'{signal.purpose}'/'{signal.channel}'"}

    existing = db.execute(
        text("""SELECT id, status, source_system, withdrawn_at FROM consents
                WHERE subject_id = CAST(:sid AS UUID) AND purpose_id = :pid AND channel_id = :chid
                  AND deleted_at IS NULL
                ORDER BY created_at DESC LIMIT 1"""),
        {"sid": subject_id, "pid": purpose_id, "chid": channel_id},
    ).mappings().first()

    new_status = "granted" if signal.granted else "withdrawn"
    ok, reason = should_apply(dict(existing) if existing else None,
                              new_status, signal.source_system)
    if not ok:
        return {"applied": False, "reason": reason,
                "consent_id": str(existing["id"]) if existing else None}

    if existing:
        consent_id = db.execute(
            text("""UPDATE consents SET status = :st, is_active = (:st = 'granted'),
                       granted_at   = CASE WHEN :st = 'granted'   THEN NOW() ELSE granted_at END,
                       withdrawn_at = CASE WHEN :st = 'withdrawn' THEN NOW() ELSE withdrawn_at END,
                       source_system = :src
                    WHERE id = CAST(:cid AS UUID) RETURNING id"""),
            {"st": new_status, "cid": existing["id"], "src": signal.source_system},
        ).scalar()
    else:
        consent_id = db.execute(
            text("""INSERT INTO consents (subject_id, purpose_id, channel_id, status,
                                          legal_basis, is_active, granted_at, withdrawn_at,
                                          source_system, created_by_system)
                    VALUES (:sid, :pid, :chid, :st, 'consent', (:st = 'granted'),
                            CASE WHEN :st = 'granted'   THEN NOW() END,
                            CASE WHEN :st = 'withdrawn' THEN NOW() END,
                            :src, :src)
                    RETURNING id"""),
            {"sid": subject_id, "pid": purpose_id, "chid": channel_id,
             "st": new_status, "src": signal.source_system},
        ).scalar()
    db.commit()

    db.execute(
        text("""INSERT INTO audit_log (entity_type, entity_id, action, actor_type,
                                       actor_id, new_values, reason)
                VALUES ('consent', :cid, :action, 'system', :src,
                        CAST(:new AS JSONB), :reason)"""),
        {"cid": str(consent_id), "action": new_status, "src": signal.source_system,
         "new": f'{{"status":"{new_status}","source":"{signal.source_system}"}}',
         "reason": f"Inbound sync from {signal.source_system}"},
    )
    db.commit()

    return {"applied": True, "reason": reason, "consent_id": str(consent_id),
            "status": new_status}
