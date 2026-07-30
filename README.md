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
