# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sentinel Privacy Platform: a centralised consent management system with four
apps sharing one database. India (DPDP Act 2023 + DPDP Rules 2025) is the
target market, not an additional one — GDPR/CCPA are secondary.

- **PMP Portal** (`apps/pmp-portal`) — customer-facing (Internet). Grant/withdraw
  consent, submit DSAR requests. Backend `pmp-backend` (FastAPI, port 8001),
  frontend `pmp-frontend` (Vite/React, port 3001).
- **IDP Console** (`apps/idp-console`) — admin/DPO portal (Intranet). Banner
  builder, consent admin, DSAR fulfilment, audit trail, webhooks, API keys.
  Backend `idp-backend` (FastAPI, port 8002), frontend `idp-frontend`
  (Vite/React, port 3002).
- **External API** (`apps/api/backend`) — partner-facing REST API + webhook
  receivers for Salesforce, HubSpot, Outreach, Highspot, etc. (port 8003). Also
  hosts the **public CMP surface** under `/api/v1/cmp` — banner config and the
  consent collector — plus JWKS at the origin root.
- **CMP loader** (`apps/cmp-loader`) — the script customers embed in their own
  websites. Vanilla TypeScript, zero dependencies, no framework, bundled by
  esbuild to a single IIFE. Not a service; it ships to a CDN.

Shared infra: PostgreSQL (consents, subjects, audit — single source of truth),
MongoDB (event history), Redis (cache + pub/sub + the webhook delivery queue),
Elasticsearch (search).

## Commands

```bash
make up          # docker compose: postgres, redis, mongo, elasticsearch + all 3 backends (built as containers)
make health      # curl the /api/v1/health endpoint on 8001/8002/8003
make admin EMAIL=you@company.com NAME="Your Name"   # create first DPO account, prints otpauth:// URI for MFA enrolment
make apikey NAME="partner" SYSTEM="salesforce"      # issue a partner API key
make web          # pnpm install + pnpm dev (both frontends)
make logs         # docker compose logs -f
make down         # stop containers, keep volumes
make reset        # docker compose down -v && up --build — wipes and re-seeds the DB
make test         # pytest for all three backends
make cmp-build    # bundle the embeddable loader (build fails above 15 KB gzipped)
make cmp-test     # drive the loader in real Chromium against a live collector
make test-all     # backends + loader
```

Running a single backend locally (not in Docker) for fast iteration:

```bash
cd apps/idp-console/idp-backend   # or apps/pmp-portal/pmp-backend, apps/api/backend
python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn src.main:app --port 8002 --reload
```

Use Python 3.12, not 3.14 — `psycopg2-binary==2.9.9` has no prebuilt wheel for
3.14 and fails to build from source (`pg_config not found`).

Single test file / test:

```bash
cd apps/idp-console/idp-backend && python3 -m pytest tests/test_auth.py -q
cd apps/idp-console/idp-backend && python3 -m pytest tests/test_auth.py::test_password_hash_roundtrip -q
```

Frontend typecheck (no separate lint script configured):

```bash
cd apps/idp-console/idp-frontend && pnpm typecheck   # tsc --noEmit
```

Applying the DB schema directly (needed if the postgres container's volume
already existed — `docker-entrypoint-initdb.d` only runs on first init of an
empty volume, so a new numbered schema file added after that won't apply
itself to an existing dev DB):

```bash
docker exec -i <postgres-container> psql -U admin -d consent_db < database/schemas/postgresql/00N_whatever.sql
```

## Architecture

**One Postgres DB, three apps.** PMP and IDP are not independently deployable
services with their own schemas — they read/write the same `consents`,
`subjects`, `banners`, `audit_log`, etc. Changing a table affects every app
that touches it; check all three `src/services/` trees before altering shared
tables.

**Schema migrations are plain numbered SQL files**, not Alembic (Alembic is
scaffolded in `database/migrations/` but `versions/` is empty and unused).
`database/schemas/postgresql/001_initial_schema.sql` is the base; later
`00N_*.sql` files are additive (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
Never edit an applied one — add a new file. All of them auto-run in order on
first boot of an empty postgres volume via the compose bind-mount into
`docker-entrypoint-initdb.d`.

**Event fan-out pattern**, used identically in pmp-backend, idp-backend, and
the external API: a service function that mutates something significant calls
`event_publisher.publish(event_type, data)`. That function LPUSHes an envelope
`{id, type, timestamp, data}` onto the Redis list `queue:webhook_delivery` and
(in pmp-backend) also PUBLISHes to `channel:<type>` / `channel:all` for
WebSocket subscribers. A single worker, `src/workers/webhook_worker.py`
(one instance is enough — it's shared infra, not per-app), BRPOPs that queue
and fans each event out to every active row in the `webhooks` table matching
`event_type`, with exponential backoff (1s→32s, 10 attempts) and a dead-letter
queue (`queue:webhook_delivery:dead`) on final failure. If you add a new
service that should notify external systems, call `event_publisher.publish`
rather than talking to `webhooks`/`webhook_deliveries` directly.

**`audit_log` is append-only** — `CREATE RULE ... ON UPDATE/DELETE DO INSTEAD
NOTHING` blocks mutation at the DB level. All writes go through
`log_audit()` in each app's `audit_service.py`.

**Services take a raw `db: Session` and hand-write SQL** via SQLAlchemy's
`text()`, returning plain dicts (`.mappings().all()` / `.mappings().first()`)
— there's no ORM model layer to keep in sync with the schema. When adding a
column, the only places it needs to show up are the schema SQL file and the
hand-written `INSERT`/`UPDATE`/`SELECT` strings that use it.

**Auth differs per app, deliberately.** idp-backend (internal, admin/DPO only)
uses static RBAC: `ROLE_PERMISSIONS` in `src/api/v1/middleware/auth.py` maps
role → permission strings (`admin` is `{"*"}`), not DB-backed. MFA (TOTP) is
mandatory for `admin`/`dpo` roles there, opt-in for `auditor`/`analyst` —
enforced in `auth_service.authenticate()`. pmp-backend (customer-facing) uses
passwordless magic-link auth instead — no roles, no password hashes. The
external API authenticates partner systems by API key
(`api_key_service`/`X-API-Key`), not user sessions at all.

**Frontend shared UI lib**: `libs/ui` (`@sentinel/ui`) is a pnpm workspace
package consumed by both frontends via Vite `resolve.alias`, not a built
package — `main`/`exports` point straight at `.ts`/`.tsx` source. When adding
aliases, the more specific path (e.g. `@sentinel/ui/styles.css`) must be
listed *before* the broader one (`@sentinel/ui`) in the alias object — Vite's
alias matcher does prefix matching in insertion order, so a broader key
declared first silently swallows the specific one.

**The CMP is a different trust boundary from the rest of the API.** Everything
under `/api/v1/cmp` is authenticated by a *publishable* key (`pk_site_*`, which
lives in the customer's page source by design) plus the browser `Origin` header
— not by a secret API key. That is why it sits on its own path prefix: it can
take different WAF and rate-limit rules at the edge. The origin allowlist is
the primary control; wildcards match exactly one label, so `https://*.acme.com`
covers `shop.acme.com` but not `a.b.acme.com` and not `evil-acme.com`.

Three constraints in that surface are easy to break by accident:

- **The publishable key must stay in the URL path** on `/collect/{key}`. A CORS
  preflight carries no custom headers — only their *names* — so a header-based
  key could never be resolved and every cross-origin POST failed closed.
- **Every response path after origin approval must carry the CORS header**,
  including bot rejections, validation errors and 429s. Without it the browser
  hides the real status and the loader sees an opaque "Failed to fetch", so a
  throttle it could back off from is indistinguishable from a network error.
- **`COLLECTOR_TRUSTED_PROXY_HOPS` must match the deployed topology.** The
  limiter counts `X-Forwarded-For` entries from the *right*, because the left
  end is written by the caller. Set it too low behind a load balancer and every
  visitor shares one bucket; set it too high and callers can spoof past the
  limit. See `.env.example` — this is a deploy-time landmine, not a preference.

**Language is evidence, not presentation.** The `languages` table holds all 22
Eighth Schedule languages plus English. The language actually served is stamped
on the consent record, because DPDP s.6(10) puts the burden of proving valid
consent on the Data Fiduciary and R.3 requires the notice version. A record
that cannot say which words the person read does not discharge that burden.
`purposes_presented` records what was on screen next to what was chosen, for
the same reason — and its values are the *pre-set state*, so a row of `false`
is the evidence that nothing was pre-ticked.

**Tag blocking has a hard limit that is a commercial fact, not a bug.**
Cooperative blocking (`type="text/plain"` + `data-sentinel-purpose`) is
guaranteed. Auto-blocking traps the `script.src` setter — a MutationObserver
alone is NOT sufficient and was measured failing, because the browser starts
fetching the moment `src` is set and observer callbacks are microtasks that
arrive afterwards. Even with the trap, a plain `<script src>` in the customer's
*served HTML* still executes: the parser runs those synchronously. Auto-block
reduces leakage; it does not make a site compliant on its own. Do not let docs,
sales material or the console imply otherwise.

**The loader has a hard size budget.** `apps/cmp-loader/build.mjs` fails the
build above 15 KB gzipped (currently 5.6 KB) because the script sits on the
customer's critical rendering path. Adding a dependency to it is a decision,
not a detail.

**Real-time propagation target is <1s** for platform/integrated-systems and
~30s for end-user browsers (CDN-cached banner config) — see the `propagation`
field returned by banner publish endpoints.
