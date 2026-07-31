# Sentinel Privacy Platform

Centralised consent management: a customer-facing preference portal (PMP), an
internal DPO console (IDP), and a partner API — over one shared database.

## Quick start

```bash
make up          # postgres + redis + mongo + all three APIs
make health      # confirm all three respond
```

Then create the first DPO account and open the console:

```bash
make admin EMAIL=you@company.com NAME="Your Name"
make web         # installs deps, runs both frontends
```

| Surface | URL |
|---|---|
| PMP portal (customers) | http://localhost:3001 |
| IDP console (internal) | http://localhost:3002 |
| PMP API docs | http://localhost:8001/docs |
| IDP API docs | http://localhost:8002/docs |
| Partner API docs | http://localhost:8003/docs |

`make admin` prints an `otpauth://` URI — scan it in your authenticator app.
MFA is mandatory for the `admin` and `dpo` roles, so you will need it to sign in.

In development, magic-link sign-in emails are printed to the PMP backend log
rather than sent, so no SMTP setup is needed:

```bash
docker compose logs -f pmp-backend
```

Run `make` on its own to see every available command.

## Resetting

```bash
make reset       # drops all data and re-applies schema + seeds
```


---

# Sentinel Privacy Platform

Enterprise Consent Management Platform with dual-portal architecture.

## Architecture

- **PMP Portal** (`apps/pmp-portal`) — Customer-facing portal (Internet). Users grant/withdraw consent, submit DSAR requests.
- **IDP Console** (`apps/idp-console`) — Admin/DPO portal (Intranet). Banner builder, consent admin, DSAR fulfillment, audit, webhooks.
- **External API** (`apps/api`) — REST API + webhook receivers for Salesforce, HubSpot, Outreach, Highspot, and custom apps.
- **Shared DB** — PostgreSQL (consents, subjects, audit) + MongoDB (event history) + Redis (cache, pub/sub) + Elasticsearch (search).
- **Real-time sync** — <1s propagation via Redis Pub/Sub + WebSocket + Kafka.

## Quick Start

```bash
# Install JS dependencies
pnpm install

# Python backends (each app)
cd apps/pmp-portal/pmp-backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Start infrastructure (postgres, redis, mongo, elasticsearch)
pnpm docker:up

# Apply database schema
psql $DATABASE_URL -f database/schemas/postgresql/001_initial_schema.sql

# Run backends
uvicorn src.main:app --port 8001 --reload   # pmp-backend
uvicorn src.main:app --port 8002 --reload   # idp-backend
uvicorn src.main:app --port 8003 --reload   # external api

# Run frontends
pnpm dev:pmp
pnpm dev:idp
```

## Repository Layout

```
apps/
  pmp-portal/     pmp-frontend (React) + pmp-backend (FastAPI)
  idp-console/    idp-frontend (React) + idp-backend (FastAPI)
  api/            backend (FastAPI) - external API + webhooks
libs/             shared TS libs (models, validation, api-client, common)
database/         SQL schemas, migrations, seeds
infrastructure/   docker, kubernetes, nginx, monitoring
docs/             architecture, API, deployment docs
```
