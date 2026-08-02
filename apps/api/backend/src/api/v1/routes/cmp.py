"""Public CMP surface: banner config and the consent collector.

Both endpoints are reachable by anyone — the publishable key is in the
customer's page source by design. The controls are the origin allowlist,
rate limiting, bot filtering and the narrow capability of the key itself:
it can read public config and write consent for its own pseudonymous bearer,
and nothing else.
"""
import json
import logging
import uuid

import redis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.services import config_service, receipt_service, site_service

router = APIRouter()

# Mounted at the origin root by main.py. RFC 8615 reserves /.well-known/ as a
# root-relative path — a JWKS client given an issuer origin will not look under
# an API version prefix, so the key set has to live outside /api/v1.
wellknown_router = APIRouter()

log = logging.getLogger(__name__)
_redis = redis.from_url(settings.redis_url, decode_responses=True)

VALID_INTERACTIONS = {"accept_all", "reject_all", "save_preferences", "close", "withdraw"}


def _client_ip(request: Request) -> str | None:
    """Resolve the caller's address, trusting only our own proxy hops.

    See site_service.client_ip — the leftmost X-Forwarded-For entry is written
    by the caller, so using it as a rate-limit key lets anyone rotate past the
    limit by changing a header.
    """
    return site_service.client_ip(
        peer=request.client.host if request.client else None,
        forwarded_for=request.headers.get("x-forwarded-for"),
        trusted_hops=settings.collector_trusted_proxy_hops,
    )


# ------------------------------------------------------------------ config

@router.get("/config/{publishable_key}")
def get_config(
    publishable_key: str,
    response: Response,
    lang: str | None = Query(None, description="Eighth Schedule language code"),
    accept_language: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Public banner config. Cacheable — contains nothing visitor-specific.

    30s TTL is a deliberate trade: a banner change reaches browsers in seconds
    rather than the sub-second the platform manages internally, without every
    page view on every customer site hitting this API.
    """
    site = site_service.get_site_by_key(db, publishable_key)
    if site is None:
        raise HTTPException(404, "Unknown site key")

    language = site_service.negotiate_language(lang, accept_language, site)
    config = config_service.build(db, site, language)

    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=300"
    response.headers["Vary"] = "Accept-Language"
    response.headers["Access-Control-Allow-Origin"] = "*"  # config is public
    return config


# --------------------------------------------------------------- collector

class CollectRequest(BaseModel):
    pseudonymous_id: str | None = Field(None, description="Omit on first visit")
    purposes: dict[str, bool] = Field(default_factory=dict)
    purposes_presented: dict[str, bool] = Field(default_factory=dict)
    interaction_type: str
    language: str | None = None
    page_url: str | None = Field(None, max_length=2000)


@router.options("/collect/{publishable_key}")
def collect_preflight(publishable_key: str, request: Request,
                      db: Session = Depends(get_db)):
    """CORS preflight, answered per-site rather than with a blanket wildcard.

    The key has to be in the path. A preflight carries no custom headers — the
    browser sends only their *names* in Access-Control-Request-Headers — so an
    earlier version that read x-site-key here could never resolve the site, and
    the preflight failed closed on every real cross-origin POST.

    This is not the authorisation point. A preflight is a browser courtesy and
    anything can skip it; the check that matters is the one on the POST below.
    """
    origin = request.headers.get("origin")
    site = site_service.get_site_by_key(db, publishable_key)
    if not site or not site_service.origin_allowed(origin, site["allowed_origins"]):
        raise HTTPException(403, "Origin not allowed")
    return Response(status_code=204, headers={
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    })


@router.post("/collect/{publishable_key}", status_code=201)
def collect(publishable_key: str, body: CollectRequest, request: Request,
            response: Response, db: Session = Depends(get_db)):
    origin = request.headers.get("origin")
    user_agent = request.headers.get("user-agent")

    site = site_service.get_site_by_key(db, publishable_key)
    if site is None:
        raise HTTPException(404, "Unknown site key")

    # Primary control. Browsers set Origin and page JS cannot forge it.
    if not site_service.origin_allowed(origin, site["allowed_origins"]):
        log.warning("collector origin rejected: site=%s origin=%s", site["slug"], origin)
        raise HTTPException(403, "Origin not allowed for this site")

    # From here on the origin is approved, so every exit — success, validation
    # error, throttle, bot — carries the CORS header. Without it the browser
    # refuses to surface the response at all and the loader sees an opaque
    # "Failed to fetch" instead of the actual status. That turns a 429 the
    # client could back off from into an indistinguishable network error.
    cors = {"Access-Control-Allow-Origin": origin or "", "Vary": "Origin"}
    response.headers.update(cors)

    if body.interaction_type not in VALID_INTERACTIONS:
        raise HTTPException(
            400, f"interaction_type must be one of {sorted(VALID_INTERACTIONS)}",
            headers=cors)

    # Crawlers are not Data Principals. Recording their consent would pollute
    # the register with records no person ever gave.
    if site_service.looks_like_bot(user_agent):
        return {"status": "ignored", "reason": "automated client"}

    ip = _client_ip(request)

    # Per-client bucket. Keyed on an address we can actually attribute — if the
    # proxy config is wrong this degrades to the socket peer rather than to a
    # caller-supplied string.
    rl_key = f"cmp:rl:{site['id']}:{ip or 'unknown'}"
    hits = _redis.incr(rl_key)
    if hits == 1:
        _redis.expire(rl_key, 60)
    if hits > settings.collector_rate_per_minute:
        raise HTTPException(429, "Rate limit exceeded",
                            headers={**cors, "Retry-After": "60"})

    # Per-site ceiling. The per-client bucket is only as good as our ability to
    # identify a client, and a botnet has many real addresses. This bounds the
    # damage one site's key can do to the consent register regardless.
    site_key_rl = f"cmp:rl:site:{site['id']}"
    site_hits = _redis.incr(site_key_rl)
    if site_hits == 1:
        _redis.expire(site_key_rl, 60)
    if site_hits > settings.collector_rate_per_site_per_minute:
        log.warning("site-wide collector ceiling hit: site=%s", site["slug"])
        raise HTTPException(429, "Rate limit exceeded",
                            headers={**cors, "Retry-After": "60"})

    # First visit mints an id; later visits present their own.
    try:
        pseudonymous_id = str(uuid.UUID(body.pseudonymous_id)) if body.pseudonymous_id \
            else str(uuid.uuid4())
    except ValueError:
        pseudonymous_id = str(uuid.uuid4())

    language = site_service.negotiate_language(
        body.language, request.headers.get("accept-language"), site)

    banner_version_id = db.execute(
        text("""SELECT bv.id FROM banner_versions bv
                JOIN banners b ON b.id = bv.banner_id
                WHERE b.id = :bid AND bv.is_current = TRUE"""),
        {"bid": str(site["banner_id"])} if site.get("banner_id") else {"bid": None},
    ).scalar() if site.get("banner_id") else None

    banner_version = db.execute(
        text("SELECT version FROM banner_versions WHERE id = :v"),
        {"v": str(banner_version_id)},
    ).scalar() if banner_version_id else None

    receipt_id = receipt_service.new_receipt_id()
    token, expires = receipt_service.sign(
        receipt_id=receipt_id, site_key=publishable_key,
        pseudonymous_id=pseudonymous_id, purposes=body.purposes,
        banner_version=banner_version, language=language,
    )

    db.execute(
        text("""
            INSERT INTO consent_receipts (receipt_id, site_id, pseudonymous_id,
                banner_version_id, language_version, purposes, purposes_presented,
                interaction_type, ip_truncated, user_agent_hash, page_url,
                signature, expires_at)
            VALUES (:rid, CAST(:site AS UUID), CAST(:pid AS UUID),
                    CAST(:bvid AS UUID), :lang, CAST(:purposes AS JSONB),
                    CAST(:presented AS JSONB), :interaction,
                    CAST(:ip AS INET), :uah, :url, :sig, :exp)
        """),
        {"rid": receipt_id, "site": str(site["id"]), "pid": pseudonymous_id,
         "bvid": str(banner_version_id) if banner_version_id else None,
         "lang": language, "purposes": json.dumps(body.purposes),
         "presented": json.dumps(body.purposes_presented),
         "interaction": body.interaction_type,
         "ip": site_service.truncate_ip(ip),
         "uah": site_service.hash_user_agent(user_agent),
         "url": body.page_url, "sig": token, "exp": expires},
    )
    db.commit()

    return {
        "receipt_id": receipt_id,
        "pseudonymous_id": pseudonymous_id,
        "receipt": token,
        "language": language,
        "expires_at": expires.isoformat(),
    }


# -------------------------------------------------------------------- jwks

@wellknown_router.get("/.well-known/jwks.json")
def jwks(response: Response):
    """Public keys, so a customer can verify a receipt without calling us."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return receipt_service.jwks()
