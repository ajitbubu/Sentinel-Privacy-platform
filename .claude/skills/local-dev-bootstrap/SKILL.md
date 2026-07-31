---
name: local-dev-bootstrap
description: Bring up Sentinel Privacy Platform locally (infra + backends + frontends) and get a logged-in admin session, for QA/dogfooding or manual verification of a change.
---

# Local dev bootstrap

The documented path (`make up`) builds and runs all three backends as
containers. That's right for a full-stack smoke test, but too slow to
iterate against when you're actively changing one backend — for that, run
the container's infra dependencies only and the one backend natively with
`--reload`.

## Full stack (containers)

```bash
make up            # postgres, redis, mongo, elasticsearch + all 3 backends, builds images
make health         # confirms 8001/8002/8003 respond
make admin EMAIL=you@company.com NAME="Your Name"   # first DPO account, prints otpauth:// URI
make web             # pnpm install + pnpm dev for both frontends (3001, 3002)
```

## One backend natively (fast iteration)

```bash
docker compose up -d postgres redis mongodb   # infra only, skip building backend images

cd apps/idp-console/idp-backend   # or pmp-portal/pmp-backend, api/backend
python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn src.main:app --port 8002 --reload
```

Use `python3.12`, not whatever `python3` resolves to — `psycopg2-binary`
has no prebuilt wheel for Python 3.14 and fails to build from source.

If `docker exec <postgres-container> psql -U admin -d consent_db -c '\dt'`
doesn't show the tables you expect, a schema file was added after the
volume's first boot and needs applying by hand (see
`rules/api-conventions.md`).

## Getting a logged-in admin session

`admin`/`dpo` roles require MFA at login, not just enrollment — there's no
way to skip it. `create_admin.py` prints an `otpauth://` URI; feed the
secret to `pyotp` to generate login codes without a real authenticator app:

```bash
python3 infrastructure/scripts/create_admin.py qa-admin@example.com --role admin --name "QA Admin"
# note the "manual entry secret" it prints

python3 -c "import pyotp; print(pyotp.TOTP('<secret>').now())"
```

`EmailStr` validation (pydantic) rejects reserved/special-use TLDs like
`.local` and `.internal` — use a normal-looking domain (`example.com`) for
test accounts.

POST that code alongside email/password to `/api/v1/auth/login`
(`mfa_code` field) to get a bearer token, or drive it through the UI: fill
email + password, submit, then fill the code on the resulting MFA prompt.

## Verifying a webhook/event-publishing change actually fired

```bash
docker exec <redis-container> redis-cli LRANGE queue:webhook_delivery 0 -1
```

The event envelope (`{id, type, timestamp, data}`) should be sitting on that
list if `event_publisher.publish()` ran successfully.
