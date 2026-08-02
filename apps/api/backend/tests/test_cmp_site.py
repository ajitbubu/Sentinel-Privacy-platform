"""Origin allowlist, language negotiation and IP truncation.

Origin validation is the primary security control on the public collector, so
it gets the most attention here.
"""
import pytest

from src.services.site_service import (
    client_ip, hash_user_agent, looks_like_bot, negotiate_language,
    origin_allowed, truncate_ip,
)

ALLOW = ["https://acme.com", "https://*.acme.co.in"]


# ---------------- origin ----------------

def test_exact_origin_allowed():
    assert origin_allowed("https://acme.com", ALLOW) is True


def test_trailing_slash_and_case_tolerated():
    assert origin_allowed("https://ACME.com/", ALLOW) is True


def test_unlisted_origin_denied():
    assert origin_allowed("https://evil.example", ALLOW) is False


def test_scheme_must_match():
    """http://acme.com must not pass an https-only allowlist — otherwise a
    downgrade gets a visitor's consent posted over plaintext."""
    assert origin_allowed("http://acme.com", ALLOW) is False


def test_single_label_wildcard_matches():
    assert origin_allowed("https://shop.acme.co.in", ALLOW) is True


def test_wildcard_does_not_match_multiple_labels():
    """*.acme.co.in must not match a.b.acme.co.in — an attacker who controls a
    sub-subdomain would otherwise inherit the parent's trust."""
    assert origin_allowed("https://a.b.acme.co.in", ALLOW) is False


def test_wildcard_does_not_match_the_bare_domain():
    assert origin_allowed("https://acme.co.in", ALLOW) is False


def test_wildcard_cannot_be_tricked_by_suffix_collision():
    """evil-acme.co.in ends with 'acme.co.in' as a string but is a different
    domain. Substring matching here would be a full bypass."""
    assert origin_allowed("https://evil-acme.co.in", ALLOW) is False


def test_empty_allowlist_denies_everything():
    """A misconfigured site must fail closed, not become an open endpoint."""
    assert origin_allowed("https://acme.com", []) is False
    assert origin_allowed("https://acme.com", None) is False


def test_missing_origin_denied():
    assert origin_allowed(None, ALLOW) is False
    assert origin_allowed("", ALLOW) is False


def test_malformed_origin_denied():
    assert origin_allowed("acme.com", ALLOW) is False
    assert origin_allowed("javascript:alert(1)", ALLOW) is False


# ---------------- language ----------------

SITE = {"available_languages": ["en", "hi", "te"], "default_language": "en"}


def test_explicit_request_wins():
    assert negotiate_language("te", "hi", SITE) == "te"


def test_unavailable_request_falls_through_to_accept_language():
    assert negotiate_language("ta", "hi,en;q=0.8", SITE) == "hi"


def test_accept_language_region_falls_back_to_base():
    """en-IN should serve the 'en' notice rather than the site default by luck."""
    assert negotiate_language(None, "en-IN,en;q=0.9", SITE) == "en"


def test_unavailable_everywhere_uses_site_default():
    assert negotiate_language("ml", "ml,ta;q=0.8", SITE) == "en"


def test_never_returns_a_language_the_site_does_not_offer():
    """Serving a language with no reviewed translation would record a notice
    version that does not exist."""
    for req, accept in [("ur", "ur"), ("xx", "yy"), (None, None)]:
        assert negotiate_language(req, accept, SITE) in SITE["available_languages"]


# ---------------- minimisation ----------------

def test_ipv4_truncated_to_24():
    assert truncate_ip("203.0.113.45") == "203.0.113.0"


def test_ipv6_truncated_to_48():
    assert truncate_ip("2001:db8:abcd:1234::1").startswith("2001:db8:abcd")


def test_invalid_ip_returns_none_rather_than_storing_junk():
    assert truncate_ip("not-an-ip") is None
    assert truncate_ip(None) is None


def test_user_agent_is_hashed_not_stored():
    ua = "Mozilla/5.0 (Macintosh)"
    h = hash_user_agent(ua)
    assert h != ua and len(h) == 64


def test_bot_detection():
    assert looks_like_bot("Googlebot/2.1") is True
    assert looks_like_bot("HeadlessChrome/120") is True
    assert looks_like_bot("Mozilla/5.0 (iPhone)") is False


# --------------------------------------------------------------- client_ip
#
# X-Forwarded-For is append-only and the left end belongs to the caller. An
# earlier version of the collector keyed its rate limiter on the leftmost
# entry, which meant rotating one header defeated the limit completely
# (measured: 400/400 requests accepted against a 120/min limit). These tests
# pin the trusted-hop semantics that replaced it.

PEER = "10.0.0.5"


def test_no_proxy_configured_ignores_forwarded_header():
    """Directly exposed: the header is decoration and must not be read."""
    assert client_ip(PEER, "1.2.3.4", 0) == PEER


def test_single_proxy_reads_the_entry_it_appended():
    assert client_ip(PEER, "203.0.113.9", 1) == "203.0.113.9"


def test_single_proxy_ignores_caller_prepended_prefix():
    """The spoof attempt sits left of our proxy's entry and is never read."""
    assert client_ip(PEER, "9.9.9.9, 203.0.113.9", 1) == "203.0.113.9"


def test_two_proxies_resolve_the_real_client():
    # CloudFront -> ALB -> us. XFF is [client, cloudfront]; peer is the ALB.
    assert client_ip(PEER, "203.0.113.9, 172.16.0.1", 2) == "203.0.113.9"


@pytest.mark.parametrize("prefix", [
    "1.1.1.1",
    "1.1.1.1, 2.2.2.2",
    "1.1.1.1, 2.2.2.2, 3.3.3.3, 4.4.4.4",
])
def test_spoofed_prefix_of_any_length_is_ignored(prefix):
    xff = f"{prefix}, 203.0.113.9, 172.16.0.1"
    assert client_ip(PEER, xff, 2) == "203.0.113.9"


def test_chain_shorter_than_configured_falls_back_to_peer():
    """Misconfiguration must not promote a caller-supplied entry to trusted."""
    assert client_ip(PEER, "203.0.113.9", 3) == PEER


def test_non_ip_value_falls_back_to_peer():
    assert client_ip(PEER, "not-an-ip, 172.16.0.1", 2) == PEER


def test_absent_forwarded_header_falls_back_to_peer():
    assert client_ip(PEER, "", 2) == PEER
    assert client_ip(PEER, None, 2) == PEER


def test_no_peer_and_no_header_is_none_not_a_crash():
    assert client_ip(None, None, 0) is None
    assert client_ip(None, None, 2) is None
