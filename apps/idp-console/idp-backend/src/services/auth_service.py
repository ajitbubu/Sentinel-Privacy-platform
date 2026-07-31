"""Admin authentication: Argon2 password hashing, TOTP MFA, brute-force lockout.

Security properties:
  - Argon2id password hashing (passlib), automatic rehash on parameter upgrade.
  - TOTP MFA (RFC 6238) mandatory for `admin` and `dpo` roles.
  - Failed-attempt lockout: 5 failures -> 15-minute lock, tracked in Redis.
  - Constant-ish response: unknown user still runs a dummy hash verification.
  - Replay protection: a TOTP code cannot be reused within its window.
"""
import secrets

import pyotp
import redis
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
_redis = redis.from_url(settings.redis_url, decode_responses=True)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 minutes
MFA_REQUIRED_ROLES = {"admin", "dpo"}

# Pre-computed hash so unknown-user logins do the same work as known-user logins.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-equalization")


class AuthError(Exception):
    """Generic auth failure — message is safe to return to the client."""


class MFARequiredError(Exception):
    """Credentials valid but an MFA code is needed."""


class AccountLockedError(Exception):
    pass


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _lock_key(email: str) -> str:
    return f"admin:failed:{email.lower()}"


def _check_lockout(email: str) -> None:
    attempts = _redis.get(_lock_key(email))
    if attempts and int(attempts) >= MAX_FAILED_ATTEMPTS:
        raise AccountLockedError(
            "Account temporarily locked after repeated failed attempts. Try again in 15 minutes."
        )


def _record_failure(email: str) -> None:
    key = _lock_key(email)
    count = _redis.incr(key)
    if count == 1:
        _redis.expire(key, LOCKOUT_SECONDS)


def _clear_failures(email: str) -> None:
    _redis.delete(_lock_key(email))


def verify_totp(secret: str, code: str, user_id: str) -> bool:
    """Verify a TOTP code with +/-1 step drift, rejecting replay of a used code."""
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False
    replay_key = f"admin:totp_used:{user_id}:{code}"
    if not _redis.set(replay_key, "1", ex=90, nx=True):
        return False  # this code was already used
    return True


def authenticate(email: str, password: str, mfa_code: str | None, db: Session) -> dict:
    """Return the user record on success. Raises AuthError / MFARequiredError / AccountLockedError."""
    email = email.strip().lower()
    _check_lockout(email)

    row = db.execute(
        text("""
            SELECT id, email, password_hash, first_name, last_name, role,
                   status, mfa_enabled, mfa_secret
            FROM users
            WHERE email = :email
        """),
        {"email": email},
    ).mappings().first()

    if row is None:
        pwd_context.verify(password, _DUMMY_HASH)  # equalize timing
        _record_failure(email)
        raise AuthError("Invalid credentials")

    user = dict(row)

    if not pwd_context.verify(password, user["password_hash"]):
        _record_failure(email)
        raise AuthError("Invalid credentials")

    if user["status"] != "active":
        raise AuthError(f"Account is {user['status']}")

    role = user["role"]
    if role in MFA_REQUIRED_ROLES and not user["mfa_enabled"]:
        raise AuthError(
            f"MFA enrollment is required for the '{role}' role. Contact an administrator."
        )

    if user["mfa_enabled"]:
        if not mfa_code:
            raise MFARequiredError("MFA code required")
        if not verify_totp(user["mfa_secret"], mfa_code, str(user["id"])):
            _record_failure(email)
            raise AuthError("Invalid MFA code")

    _clear_failures(email)
    db.execute(text("UPDATE users SET last_login_at = NOW() WHERE id = CAST(:uid AS UUID)"), {"uid": user["id"]})
    db.commit()
    return user


def enroll_mfa(user_id: str, email: str, db: Session) -> dict:
    """Generate a TOTP secret and provisioning URI. Not enabled until confirmed."""
    secret = pyotp.random_base32()
    db.execute(
        text("UPDATE users SET mfa_secret = :s, mfa_enabled = FALSE WHERE id = CAST(:uid AS UUID)"),
        {"s": secret, "uid": user_id},
    )
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.mfa_issuer)
    return {"secret": secret, "provisioning_uri": uri}


def confirm_mfa(user_id: str, code: str, db: Session) -> bool:
    """Activate MFA once the user proves they can generate a valid code."""
    secret = db.execute(
        text("SELECT mfa_secret FROM users WHERE id = CAST(:uid AS UUID)"), {"uid": user_id}
    ).scalar()
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False
    db.execute(text("UPDATE users SET mfa_enabled = TRUE WHERE id = CAST(:uid AS UUID)"), {"uid": user_id})
    db.commit()
    return True


def store_admin_refresh(user_id: str) -> str:
    import hashlib
    token = secrets.token_urlsafe(32)
    _redis.setex(
        f"admin_refresh:{hashlib.sha256(token.encode()).hexdigest()}",
        settings.refresh_token_expire_days * 86400,
        user_id,
    )
    return token


def rotate_admin_refresh(token: str) -> str | None:
    import hashlib
    user_id = _redis.getdel(f"admin_refresh:{hashlib.sha256(token.encode()).hexdigest()}")
    return user_id


def revoke_admin_refresh(token: str) -> None:
    import hashlib
    _redis.delete(f"admin_refresh:{hashlib.sha256(token.encode()).hexdigest()}")
