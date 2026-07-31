"""Consent data access. All consent SQL lives here — services stay logic-only."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_for_subject(db: Session, subject_id: str, status: str | None = None,
                     limit: int = 50, offset: int = 0) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT c.id, c.status, c.legal_basis, c.created_at, c.granted_at,
                   c.withdrawn_at, c.expires_at, c.source_system, c.metadata,
                   p.id AS purpose_id, p.name AS purpose, p.slug AS purpose_slug,
                   p.description AS purpose_description, p.is_mandatory,
                   ch.id AS channel_id, ch.name AS channel, ch.type AS channel_type
            FROM consents c
            JOIN purposes p  ON c.purpose_id = p.id
            JOIN channels ch ON c.channel_id = ch.id
            WHERE c.subject_id = :sid
              AND c.deleted_at IS NULL
              AND (:status IS NULL OR c.status = :status)
            ORDER BY c.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"sid": subject_id, "status": status, "limit": limit, "offset": offset},
    ).mappings().all()
    return [dict(r) for r in rows]


def get(db: Session, consent_id: str, subject_id: str | None = None) -> dict | None:
    row = db.execute(
        text("""
            SELECT c.*, p.name AS purpose, p.slug AS purpose_slug,
                   ch.name AS channel, ch.type AS channel_type
            FROM consents c
            JOIN purposes p  ON c.purpose_id = p.id
            JOIN channels ch ON c.channel_id = ch.id
            WHERE c.id = :cid AND c.deleted_at IS NULL
              AND (:sid IS NULL OR c.subject_id = :sid)
        """),
        {"cid": consent_id, "sid": subject_id},
    ).mappings().first()
    return dict(row) if row else None


def find_active(db: Session, subject_id: str, purpose_id: str, channel_id: str) -> dict | None:
    """Most recent non-deleted consent for this (subject, purpose, channel) triple."""
    row = db.execute(
        text("""
            SELECT * FROM consents
            WHERE subject_id = :sid AND purpose_id = :pid AND channel_id = :chid
              AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"sid": subject_id, "pid": purpose_id, "chid": channel_id},
    ).mappings().first()
    return dict(row) if row else None


def insert(db: Session, *, subject_id: str, purpose_id: str, channel_id: str,
           status: str, legal_basis: str, source_system: str,
           source_ip: str | None = None, user_agent: str | None = None,
           expires_at: Any = None, metadata: dict | None = None) -> str:
    consent_id = db.execute(
        text("""
            INSERT INTO consents (subject_id, purpose_id, channel_id, status, legal_basis,
                                  is_active, granted_at, withdrawn_at, expires_at,
                                  source_system, source_ip_address, user_agent,
                                  created_by_system, metadata)
            VALUES (:sid, :pid, :chid, :status, :basis,
                    :is_active,
                    CASE WHEN :status = 'granted'   THEN NOW() END,
                    CASE WHEN :status = 'withdrawn' THEN NOW() END,
                    :expires,
                    :source, CAST(:ip AS INET), :ua, :source, CAST(:meta AS JSONB))
            RETURNING id
        """),
        {
            "sid": subject_id, "pid": purpose_id, "chid": channel_id,
            "status": status, "basis": legal_basis,
            "is_active": status == "granted", "expires": expires_at,
            "source": source_system, "ip": source_ip, "ua": user_agent,
            "meta": json.dumps(metadata or {}),
        },
    ).scalar()
    return str(consent_id)


def update_status(db: Session, consent_id: str, status: str) -> dict | None:
    row = db.execute(
        text("""
            UPDATE consents
            SET status = :status,
                is_active = (:status = 'granted'),
                granted_at   = CASE WHEN :status = 'granted'   THEN NOW() ELSE granted_at END,
                withdrawn_at = CASE WHEN :status = 'withdrawn' THEN NOW() ELSE withdrawn_at END
            WHERE id = :cid AND deleted_at IS NULL
            RETURNING id, subject_id, purpose_id, channel_id, status, granted_at, withdrawn_at
        """),
        {"cid": consent_id, "status": status},
    ).mappings().first()
    return dict(row) if row else None


def preference_matrix(db: Session, subject_id: str) -> list[dict]:
    """Every purpose x channel combination with the subject's current state.

    LEFT JOIN so purposes the subject has never seen still appear (as 'pending'),
    which is what makes the preference centre show the full picture rather than
    only what they've already interacted with.
    """
    rows = db.execute(
        text("""
            SELECT p.id AS purpose_id, p.name AS purpose, p.slug AS purpose_slug,
                   p.description, p.is_mandatory, p.requires_explicit_consent,
                   p.retention_period_days,
                   ch.id AS channel_id, ch.name AS channel, ch.type AS channel_type,
                   c.id AS consent_id,
                   COALESCE(c.status, 'pending') AS status,
                   c.granted_at, c.withdrawn_at, c.source_system
            FROM purposes p
            CROSS JOIN channels ch
            LEFT JOIN LATERAL (
                SELECT id, status, granted_at, withdrawn_at, source_system
                FROM consents
                WHERE subject_id = :sid AND purpose_id = p.id AND channel_id = ch.id
                  AND deleted_at IS NULL
                ORDER BY created_at DESC LIMIT 1
            ) c ON TRUE
            WHERE ch.is_active = TRUE
            ORDER BY p.name, ch.name
        """),
        {"sid": subject_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def history(db: Session, subject_id: str, days: int = 365, limit: int = 200) -> list[dict]:
    """Timeline from the immutable audit log, joined to human-readable names."""
    rows = db.execute(
        text("""
            SELECT a.id, a.action, a.created_at, a.reason, a.actor_type, a.actor_id,
                   a.old_values, a.new_values,
                   p.name AS purpose, ch.name AS channel, c.source_system
            FROM audit_log a
            JOIN consents c  ON c.id = a.entity_id
            JOIN purposes p  ON c.purpose_id = p.id
            JOIN channels ch ON c.channel_id = ch.id
            WHERE a.entity_type = 'consent'
              AND c.subject_id = :sid
              AND a.created_at > NOW() - make_interval(days => :days)
            ORDER BY a.created_at DESC
            LIMIT :limit
        """),
        {"sid": subject_id, "days": days, "limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def resolve_purpose(db: Session, slug_or_id: str) -> dict | None:
    row = db.execute(
        text("SELECT id, name, slug, legal_basis_allowed, retention_period_days, is_mandatory "
             "FROM purposes WHERE slug = :v OR id::text = :v"),
        {"v": slug_or_id},
    ).mappings().first()
    return dict(row) if row else None


def resolve_channel(db: Session, name_or_id: str) -> dict | None:
    row = db.execute(
        text("SELECT id, name, type FROM channels "
             "WHERE lower(name) = lower(:v) OR type = lower(:v) OR id::text = :v"),
        {"v": name_or_id},
    ).mappings().first()
    return dict(row) if row else None
