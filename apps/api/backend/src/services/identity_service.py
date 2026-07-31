"""Identity resolution — matching an inbound signal to a subject.

Email is the join key, so normalisation decides correctness. We normalise
conservatively:
  - trim + lowercase (safe: the domain is case-insensitive by RFC, and every
    mainstream provider treats the local part case-insensitively too)
  - strip +tags and dots ONLY for the small set of providers where those are
    documented aliases (Gmail). Doing this universally would wrongly merge
    distinct people, so it is provider-scoped, not blanket.

Over-merging is the dangerous failure here: two people collapsed into one
subject means one person's withdrawal silently suppresses another's mail, or
worse, one person's DSAR export leaks the other's data.
"""
import hashlib
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

# Providers where dots and +tags are documented aliases of the same mailbox.
DOT_INSENSITIVE = {"gmail.com", "googlemail.com"}
PLUS_ALIASING = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
                 "live.com", "fastmail.com", "protonmail.com", "proton.me"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class IdentityError(Exception):
    pass


def normalize(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise IdentityError(f"Invalid email address: {email!r}")

    local, _, domain = email.partition("@")
    if domain in PLUS_ALIASING:
        local = local.split("+", 1)[0]
    if domain in DOT_INSENSITIVE:
        local = local.replace(".", "")
    if not local:
        raise IdentityError(f"Email has no local part after normalisation: {email!r}")
    return f"{local}@{domain}"


def email_hash(email: str) -> str:
    return hashlib.sha256(normalize(email).encode()).hexdigest()


EXTERNAL_ID_COLUMNS = {
    "salesforce": "salesforce_id",
    "hubspot": "hubspot_id",
    "outreach": "outreach_id",
    "highspot": "highspot_id",
}


def resolve_or_create(db: Session, email: str, *, source_system: str = "API",
                      external_id: str | None = None) -> str:
    """Return the subject id, creating the subject if this is a first sighting.

    The insert is ON CONFLICT on the normalised email, so concurrent webhooks
    for the same person converge on one row rather than racing to duplicates.
    """
    normalized = normalize(email)
    ehash = hashlib.sha256(normalized.encode()).hexdigest()

    subject_id = db.execute(
        text("""
            INSERT INTO subjects (email, email_normalized, email_hash, status,
                                  created_by_system)
            VALUES (:email, :norm, :ehash, 'active', :sys)
            ON CONFLICT (email_normalized) DO UPDATE
                SET last_activity = NOW(), updated_at = NOW()
            RETURNING id
        """),
        {"email": email.strip().lower(), "norm": normalized, "ehash": ehash,
         "sys": source_system},
    ).scalar()
    db.commit()

    column = EXTERNAL_ID_COLUMNS.get(source_system.lower())
    if column and external_id:
        # Only fill a blank — never overwrite an existing mapping, which would
        # silently repoint one CRM record at a different person.
        db.execute(
            text(f"UPDATE subjects SET {column} = :ext "  # noqa: S608 - key is allowlisted
                 "WHERE id = :sid AND (%s IS NULL OR %s = '')" % (column, column)),
            {"ext": external_id, "sid": subject_id},
        )
        db.commit()

    return str(subject_id)


def find_duplicates(db: Session, limit: int = 100) -> list[dict]:
    """Subjects sharing a normalised email — should be empty; a non-empty result
    means normalisation changed after rows were written."""
    rows = db.execute(
        text("""
            SELECT email_normalized, COUNT(*) AS count,
                   array_agg(id::text) AS subject_ids,
                   array_agg(email) AS raw_emails
            FROM subjects WHERE deleted_at IS NULL
            GROUP BY email_normalized HAVING COUNT(*) > 1
            LIMIT :limit
        """),
        {"limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]
