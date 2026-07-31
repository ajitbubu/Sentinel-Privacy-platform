---
description: Investigate and fix a bug, checking the usual failure points in this repo first
---

Investigate and fix: $ARGUMENTS

Before diving into unrelated code, check the failure points that have
actually bitten this repo before:

1. **Import-time crash on backend boot** — a service module importing
   something from `src/services/__init__.py` that was never created (e.g. a
   missing `event_publisher.py`). `uvicorn ... --reload`'s traceback will
   name the missing module directly.
2. **500 on a DB write** — `UndefinedColumn` almost always means a service's
   hand-written SQL references a column that has no matching schema
   migration, or a migration exists but was never applied to the running dev
   DB (see `rules/api-conventions.md` — schema files only auto-apply on
   first volume init).
3. **Blank/unstyled frontend page with a 500 on `index.css`** — check
   `vite.config.ts` alias ordering (`rules/code-style.md`).
4. **403 on an admin route** — check `ROLE_PERMISSIONS` for the calling
   role, and confirm the JWT's `role` claim matches what
   `require_permission` expects.

Reproduce first (curl the endpoint / load the page), read the actual
traceback or response body before guessing, then fix at the root cause.
