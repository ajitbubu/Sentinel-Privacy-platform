"""Magic-link (passwordless) authentication.

Flow:
  1. request_magic_link(email) -> secure single-use token stored (hashed) in Redis,
     15-min TTL, link emailed to the user (logged to console in development).
  2. verify_magic_link(token)  -> consumes the token, upserts the subject row,
     returns (subject_id, email) for JWT issuance.

Security properties:
  - Tokens are 256-bit URL-safe secrets; only their SHA-256 hash is stored.
  - Single use: the Redis key is deleted atomically on verification (GETDEL).
  - Rate limited: max 3 link requests per email per 15 minutes.
  - No user enumeration: the request endpoint always responds identically.
"""
import hashlib
import secrets
import smtplib
from email.message import EmailMessage

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)

MAGIC_LINK_TTL_SECONDS = settings.magic_link_expire_minutes * 60
RATE_LIMIT_MAX = 3


class RateLimitedError(Exception):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize(email: str) -> str:
    return email.strip().lower()


def request_magic_link(email: str) -> None:
    """Generate and send a magic link. Never reveals whether the email exists."""
    email = _normalize(email)

    rl_key = f"magiclink:rl:{email}"
    count = _redis.incr(rl_key)
    if count == 1:
        _redis.expire(rl_key, MAGIC_LINK_TTL_SECONDS)
    if count > RATE_LIMIT_MAX:
        raise RateLimitedError(f"Too many requests for {email}")

    token = secrets.token_urlsafe(32)
    _redis.setex(f"magiclink:{_hash(token)}", MAGIC_LINK_TTL_SECONDS, email)

    link = f"{settings.pmp_frontend_url}/verify?token={token}"
    _send_email(email, link)


def verify_magic_link(token: str, db: Session) -> tuple[str, str] | None:
    """Consume a magic-link token. Returns (subject_id, email) or None if invalid."""
    email = _redis.getdel(f"magiclink:{_hash(token)}")
    if not email:
        return None

    email_hash = hashlib.sha256(email.encode()).hexdigest()
    row = db.execute(
        text("""
            INSERT INTO subjects (email, email_normalized, email_hash,
                                  status, created_by_system)
            VALUES (:email, :email, :ehash, 'active', 'PMP')
            ON CONFLICT (email_normalized) WHERE deleted_at IS NULL DO UPDATE
                SET last_activity = NOW(), updated_at = NOW()
            RETURNING id
        """),
        {"email": email, "ehash": email_hash},
    )
    subject_id = str(row.scalar())
    db.commit()
    return subject_id, email


def store_refresh_token(subject_id: str) -> str:
    refresh = secrets.token_urlsafe(32)
    _redis.setex(
        f"refresh:{_hash(refresh)}",
        settings.refresh_token_expire_days * 86400,
        subject_id,
    )
    return refresh


def rotate_refresh_token(refresh: str) -> tuple[str, str] | None:
    """Consume old refresh token, return (subject_id, new_refresh) or None."""
    subject_id = _redis.getdel(f"refresh:{_hash(refresh)}")
    if not subject_id:
        return None
    return subject_id, store_refresh_token(subject_id)


def revoke_refresh_token(refresh: str) -> None:
    _redis.delete(f"refresh:{_hash(refresh)}")


def _send_email(email: str, link: str) -> None:
    if settings.app_env == "development" or not settings.smtp_host:
        print(f"\n{'=' * 60}\n  MAGIC LINK for {email}\n  {link}\n{'=' * 60}\n", flush=True)
        return

    msg = EmailMessage()
    msg["Subject"] = "Your sign-in link"
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(
        f"Click to sign in to your privacy preferences portal:\n\n{link}\n\n"
        f"This link expires in {settings.magic_link_expire_minutes} minutes "
        "and can be used once. If you didn't request it, ignore this email."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
