"""End-to-end CMP tests against live Postgres and Redis.

Skipped automatically when the infrastructure is not reachable, so a plain
`pytest` on a laptop with nothing running still passes. To run them:

    docker compose up -d postgres redis
    DATABASE_URL=postgresql://admin:password@localhost:5432/consent_db \
    REDIS_URL=redis://localhost:6379/0 pytest tests/test_cmp_integration.py

These cover the parts unit tests cannot: that the config the loader fetches is
actually assembled from the database, that a consent round-trips into
consent_receipts with its evidence intact, and that the receipt verifies
against the published JWKS.
"""
import json
import os
import uuid

import pytest

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/consent_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

sqlalchemy = pytest.importorskip("sqlalchemy")
redis_lib = pytest.importorskip("redis")


def _infra_up() -> bool:
    try:
        eng = sqlalchemy.create_engine(DB_URL, connect_args={"connect_timeout": 2})
        with eng.connect() as c:
            c.execute(sqlalchemy.text("SELECT 1 FROM languages LIMIT 1"))
        redis_lib.from_url(REDIS_URL, socket_connect_timeout=2).ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_up(),
    reason="needs Postgres (migrated) and Redis — see module docstring",
)

ORIGIN = "https://apollo.example.in"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "Chrome/120 Safari/537.36")


@pytest.fixture(scope="module")
def engine():
    return sqlalchemy.create_engine(DB_URL)


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DATABASE_URL", DB_URL)
    os.environ.setdefault("REDIS_URL", REDIS_URL)
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def site(engine):
    """A throwaway site with a known allowlist and language set."""
    key = f"pk_site_test_{uuid.uuid4().hex[:12]}"
    slug = f"itest-{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        sid = c.execute(sqlalchemy.text("""
            INSERT INTO sites (name, slug, publishable_key, allowed_origins,
                data_fiduciary_name, data_fiduciary_address,
                grievance_officer_name, grievance_officer_email,
                grievance_officer_phone, default_language, available_languages)
            VALUES ('Integration Test Clinic', :slug, :key,
                ARRAY['https://apollo.example.in','https://*.apollo.example.in'],
                'Apollo Clinics Pvt Ltd', '12 MG Road, Bengaluru 560001',
                'Priya Nair', 'grievance@apollo.example.in', '+91-80-4000-1234',
                'en', ARRAY['en','te','hi','ur'])
            RETURNING id
        """), {"slug": slug, "key": key}).scalar()
    yield {"id": sid, "key": key}
    with engine.begin() as c:
        c.execute(sqlalchemy.text("DELETE FROM consent_receipts WHERE site_id = :s"),
                  {"s": sid})
        c.execute(sqlalchemy.text("DELETE FROM sites WHERE id = :s"), {"s": sid})


@pytest.fixture(autouse=True)
def clean_limits():
    redis_lib.from_url(REDIS_URL).flushall()


def _post(client, site, **over):
    body = {"purposes": {"marketing": True, "analytics": False},
            "purposes_presented": {"marketing": True, "analytics": True, "essential": True},
            "interaction_type": "save_preferences", "language": "te",
            "page_url": "https://apollo.example.in/book"}
    headers = {"Origin": ORIGIN, "User-Agent": UA}
    headers.update(over.pop("headers", {}))
    body.update(over)
    return client.post("/api/v1/cmp/collect/" + site["key"], json=body, headers=headers)


# ------------------------------------------------------------------- config

def test_config_is_cacheable_and_varies_on_language(client, site):
    r = client.get(f"/api/v1/cmp/config/{site['key']}")
    assert r.status_code == 200
    assert "max-age=30" in r.headers["cache-control"]
    assert r.headers["vary"] == "Accept-Language"


def test_config_names_the_data_fiduciary_and_grievance_officer(client, site):
    """DPDP s.6(3) and s.8(9)/R.9 — the notice must say who is processing and
    who answers a complaint. The loader renders these from the config."""
    cfg = client.get(f"/api/v1/cmp/config/{site['key']}").json()
    assert cfg["data_fiduciary"]["name"] == "Apollo Clinics Pvt Ltd"
    assert cfg["data_fiduciary"]["grievance_email"] == "grievance@apollo.example.in"
    assert cfg["data_fiduciary"]["grievance_officer"] == "Priya Nair"


def test_unknown_site_key_404s(client):
    assert client.get("/api/v1/cmp/config/pk_site_nope").status_code == 404


@pytest.mark.parametrize("lang,expected", [("te", "te"), ("hi", "hi"), ("ur", "ur")])
def test_explicit_language_is_served(client, site, lang, expected):
    cfg = client.get(f"/api/v1/cmp/config/{site['key']}?lang={lang}").json()
    assert cfg["language"]["code"] == expected


def test_eighth_schedule_native_name_and_rtl(client, site):
    te = client.get(f"/api/v1/cmp/config/{site['key']}?lang=te").json()
    assert te["language"]["native_name"] == "తెలుగు"
    ur = client.get(f"/api/v1/cmp/config/{site['key']}?lang=ur").json()
    assert ur["language"]["rtl"] is True


def test_accept_language_header_is_honoured(client, site):
    cfg = client.get(f"/api/v1/cmp/config/{site['key']}",
                     headers={"Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8"}).json()
    assert cfg["language"]["code"] == "hi"


@pytest.mark.parametrize("req", ["?lang=ta", ""])
def test_language_the_site_does_not_offer_falls_back_to_default(client, site, req):
    """Never serve a language with no notice version behind it — the consent
    record would claim a translation that does not exist."""
    headers = {"Accept-Language": "fr-FR,fr;q=0.9"} if not req else {}
    cfg = client.get(f"/api/v1/cmp/config/{site['key']}{req}", headers=headers).json()
    assert cfg["language"]["code"] == "en"


# ---------------------------------------------------------------- collector

def test_consent_round_trips_with_its_evidence(client, site, engine):
    r = _post(client, site)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["language"] == "te"

    with engine.connect() as c:
        row = c.execute(sqlalchemy.text("""
            SELECT language_version, purposes, purposes_presented, interaction_type,
                   user_agent_hash, page_url
            FROM consent_receipts WHERE receipt_id = :r
        """), {"r": body["receipt_id"]}).mappings().first()

    assert row["language_version"] == "te"
    assert row["purposes"] == {"marketing": True, "analytics": False}
    # What was on screen, not merely what was chosen — s.6(10) burden of proof.
    assert set(row["purposes_presented"]) == {"marketing", "analytics", "essential"}
    assert row["user_agent_hash"] != UA and len(row["user_agent_hash"]) == 64


def test_first_visit_mints_an_id_and_a_return_visit_keeps_it(client, site):
    first = _post(client, site).json()
    again = _post(client, site, pseudonymous_id=first["pseudonymous_id"],
                  interaction_type="withdraw").json()
    assert again["pseudonymous_id"] == first["pseudonymous_id"]


def test_wildcard_subdomain_is_allowed(client, site):
    r = _post(client, site, headers={"Origin": "https://booking.apollo.example.in"})
    assert r.status_code == 201


@pytest.mark.parametrize("origin", [
    "https://evil.example.com",              # unrelated
    "http://apollo.example.in",              # scheme downgrade
    "https://apollo.example.in.evil.com",    # suffix collision
    "https://a.b.apollo.example.in",         # more than one wildcard label
])
def test_disallowed_origins_are_rejected(client, site, origin):
    assert _post(client, site, headers={"Origin": origin}).status_code == 403


def test_missing_origin_is_rejected(client, site):
    r = client.post("/api/v1/cmp/collect/" + site["key"],
                    json={"purposes": {},
                          "purposes_presented": {}, "interaction_type": "accept_all"},
                    headers={"User-Agent": UA})
    assert r.status_code == 403


def test_crawlers_do_not_enter_the_consent_register(client, site, engine):
    """A crawler is not a Data Principal; recording its consent would put a row
    in the register that no person ever gave."""
    def rows():
        with engine.connect() as c:
            return c.execute(sqlalchemy.text(
                "SELECT count(*) FROM consent_receipts WHERE site_id = :s"),
                {"s": site["id"]}).scalar()

    before = rows()
    r = _post(client, site,
              headers={"User-Agent": "Googlebot/2.1 (+http://google.com/bot.html)"})
    assert r.json()["status"] == "ignored"
    assert rows() == before, "a crawler left a row in the consent register"


def test_invalid_interaction_type_is_rejected(client, site):
    assert _post(client, site, interaction_type="nonsense").status_code == 400


# --------------------------------------------------------------- rate limits

def test_rotating_forwarded_for_does_not_bypass_the_limit(client, site):
    """Regression: keying the limiter on the leftmost X-Forwarded-For entry let
    a caller rotate one header and be accepted 400/400 against a 120/min limit."""
    from src.config.settings import settings
    accepted = sum(
        _post(client, site,
              headers={"X-Forwarded-For": f"198.51.{i // 256}.{i % 256}"}
              ).status_code == 201
        for i in range(settings.collector_rate_per_minute + 60)
    )
    assert accepted <= settings.collector_rate_per_minute


def test_limit_is_per_client_not_global(client, site, monkeypatch):
    from src.config.settings import settings
    monkeypatch.setattr(settings, "collector_trusted_proxy_hops", 1)
    for _ in range(settings.collector_rate_per_minute + 2):
        _post(client, site, headers={"X-Forwarded-For": "198.51.100.9"})
    other = _post(client, site, headers={"X-Forwarded-For": "198.51.100.10"})
    assert other.status_code == 201


def test_ip_is_truncated_not_stored_whole(client, site, engine, monkeypatch):
    from src.config.settings import settings
    monkeypatch.setattr(settings, "collector_trusted_proxy_hops", 1)
    r = _post(client, site, headers={"X-Forwarded-For": "203.0.113.47"})
    with engine.connect() as c:
        ip = c.execute(sqlalchemy.text(
            "SELECT host(ip_truncated) FROM consent_receipts WHERE receipt_id = :r"),
            {"r": r.json()["receipt_id"]}).scalar()
    assert ip == "203.0.113.0"


def test_ipv6_is_truncated_to_48(client, site, engine, monkeypatch):
    from src.config.settings import settings
    monkeypatch.setattr(settings, "collector_trusted_proxy_hops", 1)
    r = _post(client, site,
              headers={"X-Forwarded-For": "2001:db8:85a3:1234:5678:8a2e:370:7334"})
    with engine.connect() as c:
        ip = c.execute(sqlalchemy.text(
            "SELECT host(ip_truncated) FROM consent_receipts WHERE receipt_id = :r"),
            {"r": r.json()["receipt_id"]}).scalar()
    assert ip.startswith("2001:db8:85a3:") and "5678" not in ip


# ------------------------------------------------------------------ receipts

def test_receipt_verifies_against_published_jwks(client, site):
    """Asymmetric on purpose: a customer can verify a receipt we issued without
    calling us and without holding a secret of ours."""
    pyjwt = pytest.importorskip("jwt")
    from jwt import algorithms

    token = _post(client, site).json()["receipt"]
    jwks = client.get("/.well-known/jwks.json").json()
    assert len(jwks["keys"]) >= 1

    pub = algorithms.ECAlgorithm.from_jwk(json.dumps(jwks["keys"][0]))
    claims = pyjwt.decode(token, pub, algorithms=["ES256"])
    assert claims["lng"] == "te"
    assert claims["prf"] == {"marketing": True, "analytics": False}
    assert "exp" in claims


def test_tampered_receipt_does_not_verify(client, site):
    pyjwt = pytest.importorskip("jwt")
    from jwt import algorithms

    token = _post(client, site).json()["receipt"]
    jwks = client.get("/.well-known/jwks.json").json()
    pub = algorithms.ECAlgorithm.from_jwk(json.dumps(jwks["keys"][0]))

    tampered = token[:-4] + ("abcd" if not token.endswith("abcd") else "efgh")
    with pytest.raises(Exception):
        pyjwt.decode(tampered, pub, algorithms=["ES256"])


def test_jwks_is_served_from_the_origin_root(client):
    """RFC 8615 reserves /.well-known/ at the root. A verifier given an issuer
    origin looks here and will not find a key set under /api/v1."""
    assert client.get("/.well-known/jwks.json").status_code == 200
    assert client.get("/api/v1/cmp/.well-known/jwks.json").status_code == 404
