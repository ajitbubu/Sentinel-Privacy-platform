"""Conflict-resolution rules — pure function, no DB needed."""
from datetime import datetime, timedelta, timezone

from src.services.consent_service import should_apply

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _withdrawn(hours_ago: float, source: str = "PMP"):
    return {"status": "withdrawn", "source_system": source,
            "withdrawn_at": NOW - timedelta(hours=hours_ago)}


def test_first_consent_always_applies():
    apply, _ = should_apply(None, "granted", "salesforce", NOW)
    assert apply is True


def test_no_change_is_skipped():
    existing = {"status": "granted", "source_system": "PMP", "withdrawn_at": None}
    apply, reason = should_apply(existing, "granted", "PMP", NOW)
    assert apply is False and reason == "no change"


def test_stale_crm_grant_cannot_resurrect_fresh_withdrawal():
    """The core protection: someone withdraws, a lagging CRM sync must not undo it."""
    apply, reason = should_apply(_withdrawn(2), "granted", "salesforce", NOW)
    assert apply is False
    assert "conflict window" in reason


def test_user_can_resubscribe_immediately_via_portal():
    """Naive 'opt-out always wins' would break this — a real user changing their mind."""
    apply, _ = should_apply(_withdrawn(2), "granted", "PMP", NOW)
    assert apply is True


def test_crm_grant_applies_after_window_expires():
    apply, _ = should_apply(_withdrawn(48), "granted", "salesforce", NOW)
    assert apply is True


def test_withdrawal_always_beats_grant_regardless_of_source():
    existing = {"status": "granted", "source_system": "PMP", "withdrawn_at": None}
    apply, _ = should_apply(existing, "withdrawn", "hubspot", NOW)
    assert apply is True


def test_third_party_cannot_override_first_party_state():
    existing = {"status": "granted", "source_system": "PMP", "withdrawn_at": None}
    apply, reason = should_apply(existing, "withdrawn", "salesforce", NOW)
    # Withdrawals are always honoured — safety direction wins over tier
    assert apply is True


def test_naive_timestamps_are_handled():
    """DB returns naive datetimes in some configs; must not raise."""
    existing = {"status": "withdrawn", "source_system": "PMP",
                "withdrawn_at": datetime(2026, 7, 30, 10, 0)}
    apply, _ = should_apply(existing, "granted", "salesforce", NOW)
    assert apply is False
