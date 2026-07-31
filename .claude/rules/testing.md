# Testing

Each backend has its own `tests/` directory and is run from within that
app's directory — there's no shared root pytest config or conftest.

```bash
cd apps/idp-console/idp-backend && python3 -m pytest tests -q
cd apps/pmp-portal/pmp-backend && python3 -m pytest tests -q
cd apps/api/backend && python3 -m pytest tests -q

# single file / single test
python3 -m pytest tests/test_auth.py -q
python3 -m pytest tests/test_auth.py::test_password_hash_roundtrip -q
```

`make test` runs all three. Tests use `unittest.mock` to stub the DB session
rather than hitting a real Postgres — see `tests/test_auth.py` for the
pattern (`MagicMock`/`patch` on `src.services.*`).

Frontends have no test runner configured yet — `pnpm typecheck` (`tsc
--noEmit`) is the closest thing to a check, and there's no `lint` script
despite `turbo.json` declaring a `lint` task.

`ruff` is in `requirements-dev.txt` for the Python backends but has no
project config file (no `pyproject.toml`/`ruff.toml`) — running it uses
ruff's defaults.
