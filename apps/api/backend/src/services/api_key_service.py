"""API key generation and verification.

Keys look like:  sk_live_<43 url-safe chars>
Only SHA-256(key) is persisted. The plaintext is returned exactly once.
"""
import hashlib
import secrets

from sqlalchemy import text
from sqlalchemy.orm import Session

KEY_PREFIX = "sk_live_"

TIER_RATE_LIMITS = {
    "standard": 100,
    "premium": 1_000,
    "enterprise": 10_000,
}


def hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """Return (plaintext_key, key_hash, key_prefix)."""
    raw = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return raw, hash_key(raw), raw[:12]


def lookup_active_key(api_key: str, db: Session) -> dict | None:
    """Return the key record if valid, active, and unexpired; else None."""
    row = db.execute(
        text("""
            SELECT id, name, client_system, tier, scopes, allowed_ips, expires_at
            FROM api_keys
            WHERE key_hash = :kh
              AND is_active = TRUE
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
        """),
        {"kh": hash_key(api_key)},
    ).mappings().first()
    return dict(row) if row else None


def touch_last_used(key_id: str, db: Session) -> None:
    db.execute(
        text("UPDATE api_keys SET last_used_at = NOW() WHERE id = CAST(:kid AS UUID)"), {"kid": key_id}
    )
    db.commit()
