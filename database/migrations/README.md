# Migrations

Alembic-based migrations for PostgreSQL. Initial schema lives in
`database/schemas/postgresql/001_initial_schema.sql` and is auto-applied by the
docker-compose postgres entrypoint on first boot.

For subsequent changes:
1. `pip install alembic` and `alembic init` from any backend app (they share the DB)
2. Follow the expand/contract pattern: additive change -> deploy -> remove old column later
3. Never edit an applied migration; write a new one
