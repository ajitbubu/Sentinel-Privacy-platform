# API & schema conventions

## Routes

- Every backend mounts routers under `/api/v1`. idp-backend's admin surface
  is further namespaced `/api/v1/admin/<resource>` (banner authoring is the
  one exception — it's `/api/v1/banner`, not `/api/v1/admin/banner`).
- Admin routes depend on `require_permission("<verb>:<resource>")` from
  `src/api/v1/middleware/auth.py`; check `ROLE_PERMISSIONS` there before
  picking a permission string for a new route so it lines up with an
  existing role rather than inventing a one-off.

## Schema migrations

- `database/schemas/postgresql/001_initial_schema.sql` is the base schema.
  Later changes are additive, numbered SQL files
  (`00N_description.sql`, next currently free number: check the directory),
  using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Never edit an already
  merged migration file — add a new one, expand/contract style.
- These files auto-apply in filename order via the postgres container's
  `docker-entrypoint-initdb.d` bind-mount, but **only on first boot of an
  empty volume**. Against an already-initialized dev DB (e.g. after `make
  up` once), a newly added schema file must be applied by hand:
  `docker exec -i <postgres-container> psql -U admin -d consent_db < database/schemas/postgresql/00N_*.sql`.
  `make reset` is the alternative — wipes the volume and reapplies everything
  from scratch.
- `audit_log` blocks UPDATE/DELETE at the DB level (`CREATE RULE ... DO
  INSTEAD NOTHING`) — writes only ever go through `log_audit()`.

## Webhook / event fan-out

New service code that should notify partner systems calls
`event_publisher.publish(event_type, data)` rather than inserting into
`webhooks`/`webhook_deliveries` directly — that table pair is owned by
`src/workers/webhook_worker.py`, which drains the Redis queue
`queue:webhook_delivery` that `publish()` writes to.
