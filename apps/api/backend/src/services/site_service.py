"""Site lookup, origin validation and language negotiation for the CMP."""
import fnmatch
import hashlib
import ipaddress
import re
import secrets

from sqlalchemy import text
from sqlalchemy.orm import Session

KEY_PREFIX = "pk_site_"
BOT_PATTERN = re.compile(
    r"bot|crawler|spider|crawling|slurp|bingpreview|headlesschrome|"
    r"phantomjs|lighthouse|pingdom|gtmetrix|facebookexternalhit",
    re.I,
)


def generate_publishable_key() -> str:
    """Public by design — this ships in the customer's page source."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(18)}"


def get_site_by_key(db: Session, publishable_key: str) -> dict | None:
    row = db.execute(
        text("""
            SELECT s.id, s.name, s.slug, s.publishable_key, s.allowed_origins,
                   s.data_fiduciary_name, s.data_fiduciary_address,
                   s.grievance_officer_name, s.grievance_officer_email,
                   s.grievance_officer_phone,
                   s.default_language, s.available_languages,
                   s.banner_id, s.auto_block
            FROM sites s
            WHERE s.publishable_key = :key AND s.is_active = TRUE
        """),
        {"key": publishable_key},
    ).mappings().first()
    return dict(row) if row else None


def origin_allowed(origin: str | None, allowed: list[str] | None) -> bool:
    """Match an Origin header against the site's allowlist.

    Supports exact origins and a single-label wildcard (https://*.acme.com,
    which matches https://shop.acme.com but NOT https://a.b.acme.com and not
    https://acme.com itself). Browsers set Origin on cross-origin POSTs and
    page JavaScript cannot forge it, which is what makes this meaningful. It
    does not stop curl — rate limiting, bot filtering and the narrow capability
    of the publishable key handle that.

    An empty allowlist denies everything. A site that has not declared its
    origins is misconfigured, and failing open would turn it into an open
    consent-forgery endpoint.
    """
    if not allowed or not origin:
        return False

    origin = origin.strip().rstrip("/").lower()
    if "://" not in origin:
        return False
    o_scheme, o_host = origin.split("://", 1)

    for pattern in allowed:
        pattern = (pattern or "").strip().rstrip("/").lower()
        if not pattern or "://" not in pattern:
            continue
        p_scheme, p_host = pattern.split("://", 1)
        if p_scheme != o_scheme:
            continue
        if p_host == o_host:
            return True
        if p_host.startswith("*."):
            suffix = p_host[2:]
            if not suffix or not o_host.endswith("." + suffix):
                continue
            label = o_host[: -(len(suffix) + 1)]
            # exactly one extra label, and it must be non-empty
            if label and "." not in label:
                return True
    return False


def negotiate_language(requested: str | None, accept_language: str | None,
                       site: dict) -> str:
    """Choose which language version of the notice to serve.

    Order: explicit request, then Accept-Language, then the site default.
    Only ever returns a language the site actually offers — serving a notice
    in a language with no reviewed translation would be worse than serving the
    default, because the record would claim a version that does not exist.
    """
    available = [c.lower() for c in (site.get("available_languages") or ["en"])]
    default = (site.get("default_language") or "en").lower()

    if requested and requested.lower() in available:
        return requested.lower()

    for chunk in (accept_language or "").split(","):
        code = chunk.split(";")[0].strip().lower()
        if not code:
            continue
        if code in available:
            return code
        base = code.split("-")[0]           # en-IN -> en
        if base in available:
            return base
    return default


def truncate_ip(ip: str | None) -> str | None:
    """/24 for IPv4, /48 for IPv6.

    Enough to evidence the jurisdiction consent was given in, not enough to
    single a person out. DPDP has no explicit rule here; this follows the
    established data-minimisation practice.
    """
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.version == 4:
        return str(ipaddress.ip_network(f"{addr}/24", strict=False).network_address)
    return str(ipaddress.ip_network(f"{addr}/48", strict=False).network_address)


def client_ip(peer: str | None, forwarded_for: str | None, trusted_hops: int) -> str | None:
    """Resolve the real client address from the socket peer and X-Forwarded-For.

    X-Forwarded-For is append-only and fully client-controlled at the left end:
    a caller can send any prefix it likes and every proxy in front of us simply
    appends to it. Taking the leftmost entry therefore reads an attacker-supplied
    value, which is worthless as a rate-limit key — rotating it defeats the limit
    entirely.

    Only the entries our own infrastructure appended can be trusted, and there
    are exactly `trusted_hops` of them at the right-hand end. So the real client
    is the (trusted_hops + 1)-th entry counting from the right. With
    trusted_hops = 0 (no proxy in front of us) the header is ignored altogether
    and only the socket peer counts.

    Set `collector_trusted_proxy_hops` to the number of proxies that actually
    rewrite this header — for an ALB behind CloudFront that is 2. Setting it
    higher than reality reintroduces the spoof, because the count would reach
    back into entries the client supplied.
    """
    if trusted_hops <= 0:
        return peer

    hops = [h.strip() for h in (forwarded_for or "").split(",") if h.strip()]
    if not hops:
        return peer

    # Each of our N proxies appended exactly one entry, so with a chain of
    # N trusted hops the client address sits N entries from the right.
    #
    #   XFF: client, proxy1            peer = proxy2, trusted_hops = 2
    #        ^ len(hops) - 2 = index 0
    #
    # Anything the caller prepended lands further left and is never read:
    #
    #   XFF: spoof, spoof, client, proxy1      len 4 - 2 = index 2 = client
    idx = len(hops) - trusted_hops
    if idx < 0:
        # A shorter chain than configured means no entry here is provably ours.
        # Trusting one would read a client-supplied value, so use the peer.
        return peer

    candidate = hops[idx]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


def hash_user_agent(ua: str | None) -> str | None:
    """Device continuity for the audit trail, not a fingerprint."""
    return hashlib.sha256(ua.encode()).hexdigest() if ua else None


def looks_like_bot(user_agent: str | None) -> bool:
    return bool(user_agent) and bool(BOT_PATTERN.search(user_agent))
