"""API key validation tests."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.v1.middleware.api_key import _check_ip_allowlist, validate_api_key
from src.services import api_key_service


def test_generate_key_format():
    raw, key_hash, prefix = api_key_service.generate_key()
    assert raw.startswith("sk_live_")
    assert len(key_hash) == 64
    assert prefix == raw[:12]
    assert api_key_service.hash_key(raw) == key_hash


def test_keys_are_unique():
    keys = {api_key_service.generate_key()[0] for _ in range(100)}
    assert len(keys) == 100


def test_ip_allowlist_empty_allows_all():
    assert _check_ip_allowlist([], "1.2.3.4") is True
    assert _check_ip_allowlist(None, "1.2.3.4") is True


def test_ip_allowlist_blocks_unlisted():
    assert _check_ip_allowlist(["10.0.0.1"], "1.2.3.4") is False
    assert _check_ip_allowlist(["10.0.0.1"], "10.0.0.1") is True


def test_invalid_key_rejected():
    request = MagicMock()
    request.client.host = "1.2.3.4"
    with patch.object(api_key_service, "lookup_active_key", return_value=None):
        with pytest.raises(HTTPException) as exc:
            validate_api_key(request, "sk_live_bogus", MagicMock())
    assert exc.value.status_code == 403


def test_tier_rate_limits():
    assert api_key_service.TIER_RATE_LIMITS["standard"] == 100
    assert api_key_service.TIER_RATE_LIMITS["premium"] == 1_000
    assert api_key_service.TIER_RATE_LIMITS["enterprise"] == 10_000
