# OpportunityOS — Known Limitations

**Date**: October 23–24, 2026

Honest inventory of what this system does and does not do. Everything here
is either a deliberate scope decision or a known constraint — not an
oversight to be surprised by in production.

## Architecture and scope

- **Single-user personal application.** There are no user accounts, no
  ownership columns, no per-user data isolation. Whoever signs in owns
  everything. Do not host multiple people's data.
- **The scheduler is internal-only intelligence.** It discovers, normalizes,
  deduplicates, scores, plans, generates action items and syncs
  notifications. It never sends email, never submits an application, never
  approves an outreach draft, and never performs any external side effect.
  Every human-approval gate in the outreach lifecycle
  (DRAFT → PENDING_APPROVAL → APPROVED → READY_TO_SEND → SENT) is enforced
  server-side.
- **Email delivery is unconfigured by default.** With `EMAIL_HOST` empty,
  drafts stay in `READY_TO_SEND` and the send endpoint returns a clear
  error. This is intentional fail-closed behavior, and the live workflow
  test relies on it: its send attempt targets a synthetic undeliverable
  address and cannot reach a real inbox.
- **AI features are optional.** With no `AI_API_KEY`, matching stays fully
  deterministic and outreach falls back to templates. AI insight
  generation is disabled by default in the scheduler.

## Security posture

- **The sign-in token (`BFF_LOGIN_TOKEN`) is a bearer credential typed
  into a form.** Treat it like a password. It is never stored client-side,
  but it does transit the browser once over HTTPS.
- **Sessions are stateless** (`v1.<expiry>.<hmac>` cookie). There is no
  revocation list. Rotating `SESSION_SECRET` is the only force-logout:
  it invalidates every session at once. Individual logout clears only that
  browser's cookie.
- **The login rate limiter is in-process and per-process.** It resets on
  restart and does not span multiple workers. It is a speed bump, not a
  substitute for network-level protection.
- **XSS can still exercise the app as the signed-in user** (same-origin
  requests carry the HttpOnly cookie). HttpOnly prevents credential
  *exfiltration*, not same-origin *actions*. There is no per-request
  re-authentication.
- **No per-user rate limiting on API data routes** — only login is
  throttled.
- **CSRF protection** is SameSite=Lax cookies plus an Origin allowlist on
  state-changing BFF requests. Requests without an acceptable Origin get
  403; this means non-browser API clients must go through the BFF or
  carry the bearer token directly.
- **CORS restricts browsers only** and is not authentication. FastAPI
  enforces the bearer token regardless of origin; the BFF enforces the
  session regardless of origin.

## Data and matching

- **Dedup is by external ID first, canonical URL second.** A source that
  re-lists the same job under a different URL and without a stable
  external ID can produce a near-duplicate. Observed live behavior is
  clean (322 listings deduplicated exactly on re-run; 0 duplicate URL
  paths), but the guarantee is per-source-quality.
- **Live feeds drift.** External job sources add/remove listings between
  runs. "Re-run creates nothing new" is therefore not an invariant the
  system can promise; the real invariant — verified in the live workflow
  test — is that no already-seen listing is ever ingested twice.
- **Scoring is deterministic, not intelligent.** It is a transparent
  weighted rubric (skills 40, title 20, experience 15, projects 10,
  location 10, type 5) with no model, no training data, and no
  personalization beyond the stored profile preferences. Scores explain
  themselves; they do not learn.
- **Planning horizons are heuristic.** `NOW / UPCOMING / SUMMER_2027 /
  FUTURE / UNKNOWN` classification parses dates and titles; ambiguous
  postings land in `UNKNOWN` rather than guessing.
- **Exports are derived views, not backups.** Excel/CSV exports reflect
  the database at export time. Backups are `pg_dump` jobs (see DEPLOY.md).

## Testing and operations

- **The test suite needs PostgreSQL.** There is no in-memory SQLite
  fallback; `tests/conftest.py` provisions a real `opportunityos_test`
  database via the real Alembic migrations. Postgres must be running.
- **The live workflow test hits real external APIs** (Remotive,
  Arbeitnow, Himalayas). It is not hermetic: results can vary with feed
  content, and it should not be run in tight CI loops against the live
  sources.
- **The live workflow test writes to the development database** (by
  design — it drives the real stack). Its synthetic artifacts are clearly
  marked (`demo@example.com` profile, synthetic leads). The pytest suite
  never touches dev data; the live test is the one exception, and it is
  opt-in and manual.
- **Rate limits of external sources are respected but not coordinated.**
  Discovery runs are serialized by the automation engine's overlap
  protection, but manual triggers plus a scheduled run could still fetch
  close together.
- **No observability stack.** There is structured logging and health
  endpoints (`/health`, `/health/ready`) but no metrics, tracing, or
  alerting. Production monitoring is the operator's responsibility.
- **Single-node deployment.** The login rate limiter and automation
  overlap protection are in-process. Running multiple API replicas would
  weaken both; the intended deployment is one API process (optionally
  with uvicorn workers behind the same node) and one Next.js process.

## What "production-ready" means here

The DEPLOY.md checklist is the contract: TLS, secrets, backups with a
tested restore, migrations, health checks, and the post-deploy smoke
tests. Everything in this file is known, documented, and either enforced
or intentionally scoped out — none of it is hidden debt.
