"""Admin operations on consents, with a full audit trail.

A DPO acting on a Data Principal's behalf is a significant act under DPDP —
s.6(10) still requires the Data Fiduciary to prove what happened — so every
override is recorded with a mandatory reason and the fact that it bypassed
normal conflict resolution.
"""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.audit_service import log_audit

VALID_STATUSES = {"granted", "withdrawn"}


class ConsentAdminError(Exception):
    """Message is safe to surface to the caller."""


class ConsentAdminService:
    def __init__(self, db: Session):
        self.db = db

    # ---------------- search ----------------

    def search(self, subject_email: str | None = None, status: str | None = None,
               source: str | None = None, purpose: str | None = None,
               has_evidence: bool | None = None,
               page: int = 1, limit: int = 50) -> dict:
        """Cross-system consent search.

        Email match is a prefix search rather than exact: a DPO handling a
        phone enquiry has a partial address far more often than a complete one.
        """
        limit = min(max(limit, 1), 200)
        page = max(page, 1)
        where = ["c.deleted_at IS NULL"]
        params: dict = {"limit": limit, "offset": (page - 1) * limit}

        if subject_email:
            where.append("s.email_normalized LIKE LOWER(TRIM(:email)) || '%'")
            params["email"] = subject_email
        if status:
            where.append("c.status = :status")
            params["status"] = status
        if source:
            where.append("c.source_system = :source")
            params["source"] = source
        if purpose:
            where.append("p.slug = :purpose")
            params["purpose"] = purpose
        if has_evidence is True:
            where.append("c.banner_version_id IS NOT NULL")
        elif has_evidence is False:
            where.append("c.banner_version_id IS NULL")

        clause = " AND ".join(where)

        total = self.db.execute(
            text(f"""SELECT COUNT(*) FROM consents c
                     JOIN subjects s ON c.subject_id = s.id
                     JOIN purposes p ON c.purpose_id = p.id
                     WHERE {clause}"""),
            params,
        ).scalar()

        rows = self.db.execute(
            text(f"""
                SELECT c.id, s.email AS subject_email, c.subject_id,
                       p.slug AS purpose_slug, p.name AS purpose,
                       ch.name AS channel, c.status, c.legal_basis, c.source_system,
                       c.created_at, c.granted_at, c.withdrawn_at, c.is_active,
                       c.language_version, c.capture_mode, c.witness_name,
                       bv.version AS notice_version,
                       (c.banner_version_id IS NOT NULL) AS has_evidence
                FROM consents c
                JOIN subjects s  ON c.subject_id = s.id
                JOIN purposes p  ON c.purpose_id = p.id
                JOIN channels ch ON c.channel_id = ch.id
                LEFT JOIN banner_versions bv ON bv.id = c.banner_version_id
                WHERE {clause}
                ORDER BY c.created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).mappings().all()

        return {"consents": [dict(r) for r in rows], "total": total,
                "page": page, "limit": limit}

    def timeline(self, consent_id: UUID) -> dict:
        """One consent, with every recorded change. What a DPO needs when a
        Data Principal asks 'why does your system say I agreed to this?'"""
        consent = self.db.execute(
            text("""
                SELECT c.*, s.email AS subject_email, p.name AS purpose,
                       ch.name AS channel, bv.version AS notice_version,
                       bv.snapshot AS notice_snapshot
                FROM consents c
                JOIN subjects s  ON c.subject_id = s.id
                JOIN purposes p  ON c.purpose_id = p.id
                JOIN channels ch ON c.channel_id = ch.id
                LEFT JOIN banner_versions bv ON bv.id = c.banner_version_id
                WHERE c.id = CAST(:cid AS UUID) AND c.deleted_at IS NULL
            """),
            {"cid": str(consent_id)},
        ).mappings().first()
        if consent is None:
            raise ConsentAdminError("Consent not found")

        history = self.db.execute(
            text("""
                SELECT a.created_at, a.action, a.actor_type, a.actor_id, a.reason,
                       a.old_values, a.new_values, u.email AS actor_email
                FROM audit_log a
                LEFT JOIN users u ON u.id::text = a.actor_id
                WHERE a.entity_type = 'consent' AND a.entity_id = CAST(:cid AS UUID)
                ORDER BY a.created_at DESC
            """),
            {"cid": str(consent_id)},
        ).mappings().all()

        return {"consent": dict(consent), "history": [dict(h) for h in history]}

    # ---------------- override ----------------

    def admin_update(self, consent_id: UUID, status: str, reason: str,
                     actor_id: str, actor_ip: str | None = None) -> dict:
        if status not in VALID_STATUSES:
            raise ConsentAdminError(f"status must be one of {sorted(VALID_STATUSES)}")
        if not (reason or "").strip():
            raise ConsentAdminError(
                "A reason is required. Overriding a Data Principal's consent without "
                "a recorded justification cannot be defended."
            )

        old = self.db.execute(
            text("""SELECT status, is_active, source_system FROM consents
                    WHERE id = CAST(:cid AS UUID) AND deleted_at IS NULL"""),
            {"cid": str(consent_id)},
        ).mappings().first()
        if old is None:
            raise ConsentAdminError("Consent not found")

        # is_active MUST move with status. Leaving it stale means a withdrawal
        # actioned by the DPO would still read as active to any query filtering
        # on the flag — i.e. the person keeps receiving mail after opting out.
        row = self.db.execute(
            text("""
                UPDATE consents
                SET status = :status,
                    is_active = (:status = 'granted'),
                    granted_at   = CASE WHEN :status = 'granted'   THEN NOW() ELSE granted_at END,
                    withdrawn_at = CASE WHEN :status = 'withdrawn' THEN NOW() ELSE withdrawn_at END,
                    source_system = 'IDP',
                    updated_by_user_id = CAST(:actor AS UUID)
                WHERE id = CAST(:cid AS UUID) AND deleted_at IS NULL
                RETURNING id, status, is_active
            """),
            {"status": status, "actor": actor_id, "cid": str(consent_id)},
        ).mappings().first()
        self.db.commit()

        log_audit(
            self.db, entity_type="consent", entity_id=str(consent_id),
            action="admin_override", actor_id=actor_id, actor_type="user",
            actor_ip=actor_ip,
            old_values={"status": old["status"], "is_active": old["is_active"],
                        "source_system": old["source_system"]},
            new_values={"status": status, "is_active": status == "granted",
                        "source_system": "IDP",
                        "bypassed_conflict_rules": True},
            reason=reason,
        )
        return {**dict(row), "audit_logged": True}
