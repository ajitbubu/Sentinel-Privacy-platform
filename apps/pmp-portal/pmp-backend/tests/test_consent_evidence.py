"""Consent evidence rules.

DPDP s.6(10) puts the burden of proving valid consent on the Data Fiduciary and
R.3 requires the notice version to be recorded; GDPR Art. 7(1) has the same
shape. These tests cover the parts that are pure logic — the database-level
behaviour (constraint enforcement, automatic stamping) is verified separately
against a real Postgres.
"""
import pytest

from src.services.consent_rules import CAPTURE_MODES, EvidenceError, validate_evidence


def test_capture_modes_match_the_consent_register_key():
    """The Consent Register mode key is P (physical), D (digital),
    T (thumb impression with witness attestation)."""
    assert CAPTURE_MODES == {"digital", "physical", "thumb_impression_witnessed"}


def test_digital_is_the_default_and_needs_no_witness():
    validate_evidence("digital", None)  # must not raise


def test_physical_needs_no_witness():
    validate_evidence("physical", None)


def test_thumb_impression_requires_a_witness():
    """A thumb impression with no named attesting witness is not evidence."""
    with pytest.raises(EvidenceError, match="witness name is required"):
        validate_evidence("thumb_impression_witnessed", None)


def test_thumb_impression_rejects_a_blank_witness():
    """Whitespace is not a name — this is the form-submission failure mode."""
    for blank in ("", "   ", "\t\n"):
        with pytest.raises(EvidenceError, match="witness name is required"):
            validate_evidence("thumb_impression_witnessed", blank)


def test_thumb_impression_accepts_a_named_witness():
    validate_evidence("thumb_impression_witnessed", "Dr A. Sharma")


def test_unknown_capture_mode_is_rejected():
    with pytest.raises(EvidenceError, match="capture_mode must be one of"):
        validate_evidence("carrier_pigeon", None)


def test_error_message_is_safe_to_show_a_data_principal():
    """EvidenceError messages surface to the caller, so they must not leak
    internals and must tell the person what to actually do."""
    with pytest.raises(EvidenceError) as e:
        validate_evidence("thumb_impression_witnessed", None)
    msg = str(e.value)
    assert "witness" in msg.lower()
    assert "thumb impression" in msg.lower()
    assert "consents" not in msg  # no table names
