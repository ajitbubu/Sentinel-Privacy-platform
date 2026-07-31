# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sentinel Privacy Platform: a centralised consent management system with three
apps sharing one database:

- **PMP Portal** (`apps/pmp-portal`) — customer-facing (Internet). Grant/withdraw
  consent, submit DSAR requests. Backend `pmp-backend` (FastAPI, port 8001),
  frontend `pmp-frontend` (Vite/React, port 3001).
- **IDP Console** (`apps/idp-console`) — admin/DPO portal (Intranet). Banner
  builder, consent admin, DSAR fulfilment, audit trail, webhooks, API keys.
  Backend `idp-backend` (FastAPI, port 8002), frontend `idp-frontend`
  (Vite/React, port 3002).
- **External API** (`apps/api/backend`) — partner-facing REST API + webhook
  receivers for Salesforce, HubSpot, Outreach, Highspot, etc. (port 8003).

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
make test         # pytest for pmp-backend and idp-backend
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

**Real-time propagation target is <1s** for platform/integrated-systems and
~30s for end-user browsers (CDN-cached banner config) — see the `propagation`
field returned by banner publish endpoints.
