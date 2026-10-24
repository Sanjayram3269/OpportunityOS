# OpportunityOS — Verification Evidence

**Date**: October 23–24, 2026
**Environment**: Windows 11, Python 3.12 (`.venv`), Node 20, PostgreSQL 17 (local)
**Method**: every number below comes from a real run whose raw output is
committed next to this file. Nothing is estimated.

## 1. Backend test suite

| | |
|---|---|
| Command | `cd apps/api && .venv/Scripts/python.exe -m pytest -q` |
| Result | **1232 passed, 1 warning** (70.6 s) |
| Raw output | [`reports/backend_pytest_full.txt`](reports/backend_pytest_full.txt) |

The suite runs against a **dedicated test database** (`opportunityos_test`)
that `tests/conftest.py` creates, drops-and-recreates the schema for, and
re-migrates with the real Alembic chain on every run. A fail-loud guard
asserts the SQLAlchemy engine points at the test database before any test
executes. Proof of isolation: dev-database row counts were identical before
and after a full suite run.

## 2. Frontend test suite

| | |
|---|---|
| Command | `cd apps/web && npm test` |
| Result | **93 passed** across 5 files (vitest 4.1.12) |
| Suites | `app.test.tsx` (37), `bff-routes.test.ts` (31), `bff-session.test.ts` (11), `no-browser-secrets.test.ts` (6), `e2e-workflows.test.tsx` (8) |
| Raw output | [`reports/frontend_verification.txt`](reports/frontend_verification.txt) |

## 3. Static checks

| Check | Command | Result |
|---|---|---|
| Lint | `npx eslint .` | clean (exit 0, no output) |
| Types | `npx tsc --noEmit` | clean (exit 0, no output) |
| Build | `npm run build` | succeeds; all 16 routes emitted |
| Audit | `npm audit` | **0 vulnerabilities** (zod transitively bumped 4.5.4 → 4.6.7 for GHSA-mrhx-c7xc-m3w5) |

Raw output: [`reports/frontend_verification.txt`](reports/frontend_verification.txt)

## 4. Bundle secret scan

| | |
|---|---|
| Method | Every `.js/.css/.html/.txt/.json` file under `.next/static` (28 files) scanned for the **actual secret values** from `apps/api/.env` and `apps/web/.env.local` |
| Result | **0 matches** — no token or session secret value reaches the client bundle |
| Note | Scanning for secret *names* produces two false positives: user-facing help text legitimately mentions `BFF_LOGIN_TOKEN` and `API_AUTH_TOKEN` by name (login page copy, error hints). Values, not names, are the invariant. |
| Raw output | [`reports/bundle_secret_scan.txt`](reports/bundle_secret_scan.txt) |

## 5. Live end-to-end workflow (nothing mocked)

| | |
|---|---|
| Command | `apps/api/.venv/Scripts/python.exe docs/evidence/workflow/live_workflow_test.py` |
| Result | **62 passed, 0 failed** |
| Stack driven | Next.js BFF (:3000) → FastAPI (:8000) → PostgreSQL, plus live external job sources (Remotive / Arbeitnow / Himalayas) |
| Raw output | [`reports/live_workflow_log.txt`](reports/live_workflow_log.txt), [`workflow/live_workflow_results.json`](workflow/live_workflow_results.json) |

Coverage: session login and cookie flags (HttpOnly/SameSite/Secure), token
never in response bodies, live discovery ingestion (322 opportunities),
**dedup on re-run** (second automation run ingested 0 known listings —
all 322 deduplicated), deterministic scoring (integer 0–100 for every
opportunity), preference-driven rescoring (48 → 31 → 48 round-trip),
planning horizons, outreach lifecycle with approval gates, automation run
history persistence, action-generation idempotency (4 → 4 on consecutive
runs), status updates, and 401 on forged/expired sessions.

### Known-benign behavior the workflow test accounts for

- **Live feed drift**: external sources gain new listings between runs, so
  "no new opportunities on re-run" is the wrong invariant. The test asserts
  the correct one: every previously-seen `source_url` is ingested exactly
  once and never duplicated.
- **First generate catches up**: action generation legitimately adds items
  when underlying state changed since the last generate; idempotency is
  verified across two *consecutive* generates.

## 6. Test-DB isolation incident (fixed, documented)

A full pytest run originally deleted 322 real ingested opportunities from
the development database: several suites open their own committed sessions
and the dashboard/timeline suites have cleanup helpers that truncate whole
tables. The fix in `apps/api/tests/conftest.py`:

1. Derive a dedicated test database name and **refuse to run** if it would
   collide with the configured dev database.
2. Export `DATABASE_URL` pointing at it **before any `app.*` import**
   (the settings cache had to stay cold — a cached dev URL made an earlier
   isolation attempt silently run against dev).
3. Use `render_as_string(hide_password=False)` — `str(url)` masks the
   password as `***` in SQLAlchemy 2.x, which broke auth when exported.
4. Drop/recreate the schema and re-run real migrations on every run, so
   committed rows can never accumulate between runs.
5. Fail-loud guard: assert the engine points at the test database before
   the first test executes.

Dev-database row counts were verified identical before/after a full suite
run following this fix.
