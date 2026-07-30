# Architecture

See project-level docs in the EXL Consent Claude project:
- PMP-IDP-Monorepo-Structure.md — repo layout and rationale
- PMP-IDP-Implementation-Guide.md — 16-week roadmap, deployment, SLOs

Key design points:
- PMP (Internet) and IDP (Intranet) share one PostgreSQL database — single source of truth
- Real-time sync via Redis Pub/Sub + WebSocket (<1s target)
- IDP pushes config to external systems via webhook worker (queue:webhook_delivery)
- audit_log is append-only (UPDATE/DELETE blocked by rules)
