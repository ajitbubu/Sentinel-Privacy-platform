---
description: Review the current diff against this repo's schema/RBAC/audit conventions before landing
---

Review the uncommitted changes (`git diff` / `git status`) against this
repo's conventions, in order:

1. **Schema drift** — for any new/changed column referenced in a service's
   hand-written SQL (`INSERT`/`UPDATE`/`SELECT` via `text()`), confirm a
   matching `database/schemas/postgresql/00N_*.sql` migration exists and was
   added (not edited into an existing merged file). Flag any column used in
   Python that isn't in the schema files.
2. **RBAC** — for any new admin route in idp-backend, confirm it depends on
   `require_permission("<verb>:<resource>")` and that the permission string
   appears in `ROLE_PERMISSIONS` (`src/api/v1/middleware/auth.py`) for every
   role that should have it.
3. **Audit + events** — for any service function that mutates
   consent-relevant or DPO-relevant state, confirm it calls `log_audit(...)`
   and, if partner systems should hear about it, `event_publisher.publish(...)`.
4. **Vite alias ordering** — if `vite.config.ts` in either frontend changed,
   confirm more specific alias keys precede broader ones.
5. Standard correctness/security pass on the diff itself.

Report findings inline, file:line, ordered by severity. Don't restate things
that are already fine.
