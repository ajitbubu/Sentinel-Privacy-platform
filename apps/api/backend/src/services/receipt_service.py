"""Signed consent receipts (ES256).

Asymmetric on purpose. A customer must be able to verify a receipt their own
visitor presents — "did this person really consent to marketing?" — without
holding a shared secret. HMAC would require distributing a key that also lets
them *mint* receipts, which defeats the point of the receipt as evidence.

The receipt does three jobs:
  1. the loader renders correct state on the next page load with no network call
  2. the customer's backend verifies consent independently, offline
  3. tampering is detectable — editing localStorage breaks the signature

Key handling: RECEIPT_PRIVATE_KEY (PEM) in every real environment. In
development an ephemeral key is generated at import and loudly logged, because
silently signing with a throwaway key that changes on restart would make
receipts mysteriously fail to verify.
"""
import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwt

from src.config.settings import settings

log = logging.getLogger(__name__)

ALGORITHM = "ES256"
RECEIPT_TTL_DAYS = 365  # consent expiry; see re-consent rules


def _load_or_generate_key():
    pem = (settings.receipt_private_key or "").strip()
    if pem:
        return serialization.load_pem_private_key(pem.encode(), password=None)
    if settings.app_env == "production":
        raise RuntimeError(
            "RECEIPT_PRIVATE_KEY is required in production. Receipts signed with an "
            "ephemeral key cannot be verified after a restart."
        )
    log.warning(
        "No RECEIPT_PRIVATE_KEY set — generating an ephemeral P-256 key. "
        "Receipts will stop verifying when this process restarts. Development only."
    )
    return ec.generate_private_key(ec.SECP256R1())


_private_key = _load_or_generate_key()
_public_key = _private_key.public_key()


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _jwk() -> dict:
    nums = _public_key.public_numbers()
    x = _b64u(nums.x.to_bytes(32, "big"))
    y = _b64u(nums.y.to_bytes(32, "big"))
    # RFC 7638 thumbprint: stable kid across restarts for the same key
    canonical = json.dumps({"crv": "P-256", "kty": "EC", "x": x, "y": y},
                           separators=(",", ":"), sort_keys=True)
    kid = _b64u(hashlib.sha256(canonical.encode()).digest())
    return {"kty": "EC", "crv": "P-256", "x": x, "y": y,
            "use": "sig", "alg": ALGORITHM, "kid": kid}


JWK = _jwk()
KID = JWK["kid"]

_pem_private = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_pem_public = _public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()


def jwks() -> dict:
    """Public key set. Customers fetch this to verify receipts themselves."""
    return {"keys": [JWK]}


def public_key_pem() -> str:
    return _pem_public


def new_receipt_id() -> str:
    return f"rcpt_{secrets.token_urlsafe(12)}"


def sign(*, receipt_id: str, site_key: str, pseudonymous_id: str,
         purposes: dict, banner_version: int | None, language: str | None,
         issued_at: datetime | None = None) -> tuple[str, datetime]:
    """Return (jwt, expires_at).

    Claims are short because this rides in a cookie on every page: rid, sid,
    pid, prf, bv, lng, iat, exp.
    """
    now = issued_at or datetime.now(timezone.utc)
    expires = now + timedelta(days=RECEIPT_TTL_DAYS)
    payload = {
        "rid": receipt_id,
        "sid": site_key,
        "pid": pseudonymous_id,
        "prf": purposes,
        "bv": banner_version,
        "lng": language,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, _pem_private, algorithm=ALGORITHM,
                       headers={"kid": KID})
    return token, expires


def verify(token: str) -> dict | None:
    """Verify a receipt. Returns claims, or None if invalid or expired."""
    try:
        return jwt.decode(token, _pem_public, algorithms=[ALGORITHM])
    except Exception:
        return None
