"""DPO override rules.

A DPO acting on a Data Principal's behalf is a significant act: DPDP s.6(10)
still requires the Data Fiduciary to prove what happened.
"""
from unittest.mock import MagicMock

import pytest

from src.services.consent_admin_service import (
    VALID_STATUSES, ConsentAdminError, ConsentAdminService,
)


def _svc():
    return ConsentAdminService(MagicMock())


def test_only_granted_or_withdrawn_can_be_set_by_an_admin():
    """An admin must not be able to park a consent in 'pending' or 'expired' —
    those are states the system derives, not states a person chooses."""
    assert VALID_STATUSES == {"granted", "withdrawn"}
    with pytest.raises(ConsentAdminError, match="status must be one of"):
        _svc().admin_update("00000000-0000-0000-0000-000000000000", "expired",
                            "a valid reason here", actor_id="u1")


def test_reason_is_mandatory():
    with pytest.raises(ConsentAdminError, match="reason is required"):
        _svc().admin_update("00000000-0000-0000-0000-000000000000", "withdrawn",
                            "", actor_id="u1")


def test_whitespace_only_reason_is_rejected():
    """The realistic failure is a form submitting spaces, not an empty string."""
    for blank in ("   ", "\t", "\n\n"):
        with pytest.raises(ConsentAdminError, match="reason is required"):
            _svc().admin_update("00000000-0000-0000-0000-000000000000", "withdrawn",
                                blank, actor_id="u1")


def test_missing_consent_raises_rather_than_crashing():
    """The previous implementation called dict() on a None row."""
    svc = _svc()
    svc.db.execute.return_value.mappings.return_value.first.return_value = None
    with pytest.raises(ConsentAdminError, match="not found"):
        svc.admin_update("00000000-0000-0000-0000-000000000000", "withdrawn",
                         "a valid reason here", actor_id="u1")


def test_reason_message_explains_why_not_just_that():
    with pytest.raises(ConsentAdminError) as e:
        _svc().admin_update("00000000-0000-0000-0000-000000000000", "withdrawn",
                            "", actor_id="u1")
    assert "defended" in str(e.value)
