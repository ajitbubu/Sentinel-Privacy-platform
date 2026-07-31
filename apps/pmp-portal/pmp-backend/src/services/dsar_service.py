"""Data Subject Access Requests — submission and status for the PMP side."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services import event_publisher
from src.services.audit_service import log_audit

# GDPR Art. 12(3): one month, extendable by two further months.
FULFILMENT_DAYS = 30

VALID_TYPES = {"access", "deletion", "rectification", "export", "portability"}


class DSARError(Exception):
    pass


def create(db: Session, *, subject_id: str, request_type: str,
           description: str | None = None, created_by_system: str = "PMP",
           actor_id: str | None = None) -> dict:
    if request_type not in VALID_TYPES:
        raise DSARError(f"request_type must be one of {sorted(VALID_TYPES)}")

    # Duplicate guard — an identical open request is almost always a double-click.
    existing = db.execute(
        text("""
            SELECT id FROM dsar_requests
            WHERE subject_id = CAST(:sid AS UUID) AND request_type = :rt
              AND status IN ('submitted', 'acknowledged', 'in_progress')
        """),
        {"sid": subject_id, "rt": request_type},
    ).scalar()
    if existing:
        raise DSARError(
            f"You already have an open '{request_type}' request. "
            "We'll email you when it's complete."
        )

    due = datetime.now(timezone.utc) + timedelta(days=FULFILMENT_DAYS)
    row = db.execute(
        text("""
            INSERT INTO dsar_requests (subject_id, request_type, description,
                                       status, due_date, created_by_system)
            VALUES (:sid, :rt, :desc, 'submitted', :due, :sys)
            RETURNING id, request_type, status, submitted_at, due_date
        """),
        {"sid": subject_id, "rt": request_type, "desc": description,
         "due": due, "sys": created_by_system},
    ).mappings().first()
    db.commit()

    result = dict(row)
    dsar_id = str(result["id"])

    log_audit(db, entity_type="dsar", entity_id=dsar_id, action="create",
              actor_id=actor_id or subject_id,
              new_values={"request_type": request_type, "due_date": due.isoformat()})

    event_publisher.publish("dsar.created", {
        "dsar_id": dsar_id, "subject_id": subject_id,
        "request_type": request_type, "due_date": due.isoformat(),
    })
    return result


def list_for_subject(db: Session, subject_id: str) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT id, request_type, status, description, submitted_at, due_date,
                   fulfilled_at, denial_reason, response_download_expires_at
            FROM dsar_requests
            WHERE subject_id = CAST(:sid AS UUID)
            ORDER BY submitted_at DESC
        """),
        {"sid": subject_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def get(db: Session, dsar_id: str, subject_id: str) -> dict | None:
    row = db.execute(
        text("""
            SELECT id, request_type, status, description, submitted_at, due_date,
                   fulfilled_at, denial_reason, response_method,
                   response_download_expires_at
            FROM dsar_requests
            WHERE id = CAST(:did AS UUID) AND subject_id = CAST(:sid AS UUID)
        """),
        {"did": dsar_id, "sid": subject_id},
    ).mappings().first()
    if row is None:
        return None
    result = dict(row)
    result["days_remaining"] = _days_remaining(result)
    return result


def _days_remaining(dsar: dict) -> int | None:
    if dsar["status"] in ("fulfilled", "denied", "cancelled"):
        return None
    due = dsar["due_date"]
    if due is None:
        return None
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return max(0, (due - datetime.now(timezone.utc)).days)


def cancel(db: Session, dsar_id: str, subject_id: str) -> bool:
    updated = db.execute(
        text("""
            UPDATE dsar_requests SET status = 'cancelled'
            WHERE id = CAST(:did AS UUID) AND subject_id = CAST(:sid AS UUID)
              AND status IN ('submitted', 'acknowledged')
            RETURNING id
        """),
        {"did": dsar_id, "sid": subject_id},
    ).scalar()
    if not updated:
        return False
    db.commit()
    log_audit(db, entity_type="dsar", entity_id=dsar_id, action="cancel",
              actor_id=subject_id)
    return True
