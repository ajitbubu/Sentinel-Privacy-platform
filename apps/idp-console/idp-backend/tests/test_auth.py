"""Admin auth: password hashing, MFA, lockout, role permissions."""
from unittest.mock import MagicMock, patch

import pytest

from src.api.v1.middleware.auth import ROLE_PERMISSIONS
from src.services import auth_service


def test_password_hash_roundtrip():
    h = auth_service.hash_password("correct-horse-battery")
    assert h != "correct-horse-battery"
    assert h.startswith("$argon2")
    assert auth_service.pwd_context.verify("correct-horse-battery", h)
    assert not auth_service.pwd_context.verify("wrong", h)


def test_hashes_are_salted():
    a = auth_service.hash_password("same-password")
    b = auth_service.hash_password("same-password")
    assert a != b  # distinct salts


def test_mfa_required_roles():
    assert "admin" in auth_service.MFA_REQUIRED_ROLES
    assert "dpo" in auth_service.MFA_REQUIRED_ROLES
    assert "auditor" not in auth_service.MFA_REQUIRED_ROLES


def test_unknown_user_raises_auth_error():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.first.return_value = None
    with patch.object(auth_service, "_check_lockout"), \
         patch.object(auth_service, "_record_failure"):
        with pytest.raises(auth_service.AuthError):
            auth_service.authenticate("nobody@x.com", "pw", None, db)


def test_valid_password_without_mfa_code_raises_mfa_required():
    pw_hash = auth_service.hash_password("valid-password-123")
    db = MagicMock()
    db.execute.return_value.mappings.return_value.first.return_value = {
        "id": "uuid-1", "email": "dpo@x.com", "password_hash": pw_hash,
        "first_name": "D", "last_name": "PO", "role": "dpo",
        "status": "active", "mfa_enabled": True, "mfa_secret": "BASE32SECRET",
    }
    with patch.object(auth_service, "_check_lockout"):
        with pytest.raises(auth_service.MFARequiredError):
            auth_service.authenticate("dpo@x.com", "valid-password-123", None, db)


def test_dpo_without_mfa_enrolled_is_blocked():
    pw_hash = auth_service.hash_password("valid-password-123")
    db = MagicMock()
    db.execute.return_value.mappings.return_value.first.return_value = {
        "id": "uuid-1", "email": "dpo@x.com", "password_hash": pw_hash,
        "first_name": "D", "last_name": "PO", "role": "dpo",
        "status": "active", "mfa_enabled": False, "mfa_secret": None,
    }
    with patch.object(auth_service, "_check_lockout"):
        with pytest.raises(auth_service.AuthError, match="MFA enrollment"):
            auth_service.authenticate("dpo@x.com", "valid-password-123", None, db)


def test_role_permission_boundaries():
    assert ROLE_PERMISSIONS["admin"] == {"*"}
    assert "write:banner" in ROLE_PERMISSIONS["dpo"]
    assert "write:banner" not in ROLE_PERMISSIONS["auditor"]
    assert "write:consent_admin" not in ROLE_PERMISSIONS["analyst"]
    assert "read:audit" in ROLE_PERMISSIONS["auditor"]


def test_totp_verification():
    import pyotp
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    fake_redis = MagicMock()
    fake_redis.set.return_value = True  # not replayed
    with patch.object(auth_service, "_redis", fake_redis):
        assert auth_service.verify_totp(secret, code, "user-1") is True
        assert auth_service.verify_totp(secret, "000000", "user-1") is False


def test_totp_replay_rejected():
    import pyotp
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    fake_redis = MagicMock()
    fake_redis.set.return_value = None  # key already exists -> replay
    with patch.object(auth_service, "_redis", fake_redis):
        assert auth_service.verify_totp(secret, code, "user-1") is False
