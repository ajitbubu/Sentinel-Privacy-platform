# Code style

## Python backends (pmp-backend, idp-backend, api/backend)

- No ORM models. Services take `db: Session` and hand-write SQL with
  SQLAlchemy's `text()`, returning plain dicts via `.mappings().all()` /
  `.mappings().first()`. Follow this pattern for new service functions —
  don't introduce declarative models for part of the schema.
- Adding a column means updating it in exactly two places: the schema SQL
  file (new numbered migration, see `rules/api-conventions.md`) and every
  hand-written `INSERT`/`UPDATE`/`SELECT` string that should carry it. There
  is no model to keep in sync, but also no model to catch a missed spot —
  grep for the table name before considering a schema change done.
- Significant mutations call `event_publisher.publish(event_type, data)`
  (fire-and-forget onto the Redis webhook queue) and `log_audit(...)` (durable
  audit trail). If you add a service function that changes something a DPO or
  partner system would care about, wire both in rather than one.
- Target Python 3.12 for local venvs. 3.14 breaks `psycopg2-binary`'s build.

## Frontend (pmp-frontend, idp-frontend)

- `@sentinel/ui` (`libs/ui`) is consumed as workspace source via a Vite
  `resolve.alias`, not a built package. When editing `vite.config.ts` alias
  maps, list more specific paths (`@sentinel/ui/styles.css`) *before* broader
  ones (`@sentinel/ui`) — Vite matches aliases by prefix in insertion order,
  so the broader key silently wins if it comes first.
- Tailwind v4 (`@tailwindcss/vite` plugin, no `tailwind.config.js`) + shared
  theme in `libs/ui/src/styles/theme.css`.
