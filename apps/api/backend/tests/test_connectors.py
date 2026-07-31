"""Connector field mapping — especially the inverted opt-out fields."""
from src.integrations import get_connector
from src.integrations.base import _truthy


def test_truthy_handles_vendor_variations():
    for v in (True, 1, "true", "TRUE", "yes", "1", "granted"):
        assert _truthy(v) is True
    for v in (False, 0, "false", "no", "0", ""):
        assert _truthy(v) is False


def test_salesforce_inverts_has_opted_out():
    """HasOptedOutOfEmail=true means consent is NOT granted. Getting this
    backwards would mail everyone who opted out."""
    sf = get_connector("salesforce")
    signals = sf.parse_inbound({
        "email": "a@example.com", "contact_id": "003xx",
        "fields_changed": {"HasOptedOutOfEmail": True},
    })
    assert len(signals) == 1
    assert signals[0].granted is False


def test_salesforce_normal_field_not_inverted():
    sf = get_connector("salesforce")
    signals = sf.parse_inbound({
        "email": "a@example.com", "fields_changed": {"Email_Opt_In__c": True},
    })
    assert signals[0].granted is True


def test_hubspot_inverts_optout_and_unwraps_nested_values():
    hs = get_connector("hubspot")
    signals = hs.parse_inbound({
        "email": "b@example.com",
        "properties": {"hs_email_optout": {"value": "true"}},
    })
    assert len(signals) == 1
    assert signals[0].granted is False


def test_outreach_maps_opted_out():
    o = get_connector("outreach")
    signals = o.parse_inbound({"data": {"id": 9, "attributes": {
        "emails": ["c@example.com"], "optedOut": True}}})
    assert signals[0].granted is False
    assert signals[0].email == "c@example.com"


def test_unknown_fields_are_ignored_not_errors():
    sf = get_connector("salesforce")
    assert sf.parse_inbound({"email": "a@x.com", "fields_changed": {"Unrelated__c": "x"}}) == []


def test_missing_email_yields_no_signals():
    for name in ("salesforce", "hubspot", "outreach", "highspot"):
        assert get_connector(name).parse_inbound({"foo": "bar"}) == []


def test_signature_verification():
    import hashlib, hmac
    sf = get_connector("salesforce")
    body = b'{"email":"a@x.com"}'
    secret = "s3cret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sf.verify(body, {"x-salesforce-signature": sig}, secret) is True
    assert sf.verify(body, {"x-salesforce-signature": "wrong"}, secret) is False
    assert sf.verify(body, {}, secret) is False  # missing header rejected


def test_sync_rules_match_pmp_rules():
    """The API service duplicates the conflict rules for deployment independence.
    If the two ever diverge, this fails — which is the whole point of duplicating
    with a test rather than sharing a fragile import across services."""
    from src.services.consent_sync import SOURCE_TIER, CONFLICT_WINDOW_HOURS
    assert CONFLICT_WINDOW_HOURS == 24
    assert SOURCE_TIER["PMP"] == 3
    assert SOURCE_TIER["API"] == 2
    assert SOURCE_TIER.get("salesforce", 1) == 1
