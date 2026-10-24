# OpportunityOS — Deployment Guide

## Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 17+ (or Docker)
- Git

## Quick Start (Development)

### 1. Start PostgreSQL

```bash
cd infra/postgres
cp .env.example .env  # Edit POSTGRES_PASSWORD
docker compose up -d
```

### 2. Backend Setup

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env — set DATABASE_URL to match your PostgreSQL
# Set API_AUTH_TOKEN (see "Authentication" below), e.g.:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd apps/web
npm install

# Create .env.local for the BFF (server-only values — see
# apps/web/.env.example for the annotated template):
#   API_BASE_URL=http://localhost:8000
#   API_AUTH_TOKEN=<same token as the API's API_AUTH_TOKEN>
#   BFF_LOGIN_TOKEN=<token you will paste at http://localhost:3000/login>
#   SESSION_SECRET=<32+ chars, e.g. node -e "console.log(require('crypto').randomBytes(32).toString('hex'))">
#   SESSION_TTL_HOURS=12
#   BFF_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
cp .env.example .env.local  # then edit the values

# Start dev server
npm run dev
```

### 4. Verify

- API health: http://localhost:8000/health
- API readiness: http://localhost:8000/health/ready
- API docs (dev only): http://localhost:8000/docs
- Frontend: http://localhost:3000 (sign in at http://localhost:3000/login
  with `BFF_LOGIN_TOKEN`)

## Production Deployment

### Environment Variables

Copy `.env.example` to `.env` and configure:

Backend (`apps/api/.env`):

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection URL |
| `API_AUTH_TOKEN` | ✅ | Bearer token required on every API route except `/health*`. **Server-to-server only** — attached by the BFF; never sent to a browser |
| `ENVIRONMENT` | ✅ | Set to `production` |
| `DEBUG` | ✅ | Set to `false` |
| `CORS_ORIGINS` | ✅ | Your frontend domain(s) |
| `AI_API_KEY` | Optional | AI provider key |
| `EMAIL_HOST` | Optional | SMTP server for email delivery |

Frontend server runtime (`apps/web/.env.local`, read by route handlers at
request time — **no build-time variables, nothing inlined into the
bundle**). See `apps/web/.env.example` for the annotated template:

| Variable | Required | Description |
|---|---|---|
| `API_BASE_URL` | ✅ | FastAPI origin the BFF proxies to (e.g. `http://127.0.0.1:8000`) |
| `API_AUTH_TOKEN` | ✅ | Same value as backend `API_AUTH_TOKEN`; attached by the BFF server-side |
| `BFF_LOGIN_TOKEN` | ✅ | Sign-in token pasted at `/login`; exchanged for an HttpOnly session cookie |
| `SESSION_SECRET` | ✅ | HMAC secret for session cookies, **32+ chars**. Rotating it invalidates all sessions |
| `SESSION_TTL_HOURS` | Optional | Session lifetime (default `12`) |
| `BFF_UPSTREAM_TIMEOUT_SECONDS` | Optional | BFF → API request timeout (default `180`); must exceed a full automation run |
| `BFF_ALLOWED_ORIGINS` | ✅ (prod) | Comma-separated origins for CSRF Origin checks; must be set in production |

## Authentication (BFF / session-cookie architecture)

```
Browser ── HttpOnly session cookie ──> Next.js BFF (/api/bff/*) ── Bearer API_AUTH_TOKEN ──> FastAPI
         (never sees any token)         (allowlist + CSRF + session)     (require_auth, fail-closed)
```

- **The browser never holds the FastAPI bearer token.** All API traffic
  goes through the Next.js BFF (`/api/bff/*`), which attaches
  `Authorization: Bearer <API_AUTH_TOKEN>` server-side after validating
  the session. No `NEXT_PUBLIC_*` secret exists; the token appears in no
  frontend bundle.
- **Sign-in:** `POST /api/auth/login` compares the pasted token against
  server-only `BFF_LOGIN_TOKEN` in constant time (rate-limited: 5 failures
  / 15 min per client) and sets an **HttpOnly, SameSite=Lax
  (Secure in production)** session cookie signed with HMAC-SHA256 over
  `SESSION_SECRET`, carrying its own expiry. `GET /api/auth/session`
  reports validity; `POST /api/auth/logout` clears the cookie.
- **Session integrity:** the cookie value is `v1.<expiry>.<hmac>`; the BFF
  verifies the HMAC (constant time) and expiry on every request. Tampered,
  expired, or forged cookies get `401`. There is no server-side session
  store — rotating `SESSION_SECRET` invalidates every session at once.
- **Proxy allowlist:** only explicit path+method pairs used by the app are
  proxied (see `apps/web/src/lib/server/proxy.ts`). Unknown paths get
  `404`, wrong methods `405`; path segments are charset-restricted so
  traversal (`..`, encoded separators) is structurally impossible; the
  upstream origin comes only from `API_BASE_URL` (no open proxy). Client
  `Authorization`/`Cookie` headers are never forwarded upstream.
- **CSRF:** state-changing requests require an `Origin` header on the
  `BFF_ALLOWED_ORIGINS` allowlist (missing/wrong → `403`), on top of the
  SameSite=Lax cookie which browsers won't attach to cross-site writes.
- **Fail closed everywhere:** empty `API_AUTH_TOKEN` → proxy `503`; empty
  `BFF_LOGIN_TOKEN`/short-or-empty `SESSION_SECRET` → login `503`; missing
  `BFF_ALLOWED_ORIGINS` in production → `503`. No hardcoded fallback
  secret or token exists anywhere in the codebase.
- **FastAPI unchanged:** every route except `GET /health` and
  `GET /health/ready` still requires `Authorization: Bearer
  <API_AUTH_TOKEN>` with constant-time comparison; in production
  (`ENVIRONMENT=production`) `/docs`, `/redoc` and `/openapi.json` are
  disabled.

Generate secrets (never commit them):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # API_AUTH_TOKEN / BFF_LOGIN_TOKEN
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"  # SESSION_SECRET
```

### Threat model and limitations (read this)

**What the BFF architecture defends against:**

- Token theft from the browser: the FastAPI bearer token exists only in
  server-side env vars and server memory; it is in no bundle, no
  localStorage, no network response.
- Session theft via XSS *reading* the credential: the cookie is HttpOnly,
  so script cannot read it. (XSS can still *act* as the user through the
  same-origin DOM — HttpOnly is not an XSSmitigation for actions, only for
  credential exfiltration.)
- CSRF: SameSite=Lax cookie + Origin allowlist on state-changing requests.
- Open proxying / SSRF via the proxy: fixed upstream origin, explicit
  path+method allowlist, charset-restricted segments (no traversal).
- Brute force of the sign-in token: rate-limited (5 failures / 15 min per
  client, in-memory per process).

**Limitations (unchanged or new — do not overlook):**

- Still a **single-user personal application**: no user accounts, no
  per-user ownership columns, no data isolation. Anyone who signs in has
  full owner access. Do not host multiple people's data.
- The sign-in token (`BFF_LOGIN_TOKEN`) is a bearer credential typed into
  the login form. Treat it like a password; it transits the browser once
  (over HTTPS) but is never stored client-side.
- Sessions are **stateless**: there is no revocation list. To force-logout
  all sessions, rotate `SESSION_SECRET` (all cookies instantly fail HMAC
  verification) and restart the Next.js server. Individual session logout
  only clears that browser's cookie.
- The login rate limiter is in-memory per process and resets on restart;
  it is a speed bump, not a substitute for network-level protection.
- XSS can still exercise the app as the signed-in user (same-origin
  requests carry the cookie). Keep dependencies audited; there is no
  per-request re-authentication.
- No per-user rate limiting on API data routes — only login is throttled.
- CORS restricts *browsers* only and is **not** authentication; the BFF
  additionally enforces the session, and FastAPI enforces the bearer token
  regardless of origin.
- Health endpoints stay public for load-balancer probes and expose only
  liveness/readiness status (no data, no secrets).
- npm dependency advisories are tracked with `npm audit` in `apps/web`;
  run it before every production build and remediate critical/high findings.

### HTTPS requirements

- In production (`NODE_ENV=production`) the session cookie is **Secure**;
  browsers will only send it over HTTPS. Serve the Next.js app behind TLS.
- With plain HTTP in production, sign-in appears to succeed but the cookie
  is never returned by the browser — every page redirects back to
  `/login`. This is intentional fail-closed behavior.
-  Terminate TLS at a reverse proxy (Caddy/Nginx/Cloudflare) and set
  `BFF_ALLOWED_ORIGINS=https://your-domain.com`.

### Secret rotation runbook

There are now **three server-side secrets**; rotate any of them when
exposure is suspected (shared screen, checked-out laptop, repo leak). No
frontend rebuild is ever required — secrets are read at request time, not
baked into a bundle.

1. **`API_AUTH_TOKEN`** (FastAPI ↔ BFF):
   1. Generate a new token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   2. Set it in `apps/api/.env` **and** `apps/web/.env.local`, restart both
      processes. The old token stops working immediately on the API side.
   3. Verify: `curl -s -o /dev/null -w "%{http_code}\n" http://<api>/profiles`
      → `401`; with the new token in the `Authorization` header → `200`.
2. **`BFF_LOGIN_TOKEN`** (sign-in credential):
   1. Generate a new value, update `apps/web/.env.local`, restart the web
      server. The old value is rejected at `/login` immediately.
   2. Existing sessions stay valid until expiry (they don't embed the
      login token). To cut them off too, also rotate `SESSION_SECRET`.
3. **`SESSION_SECRET`** (session signing key — **the kill switch**):
   1. Generate a new 32+ char value, update `apps/web/.env.local`, restart
      the web server.
   2. **Every active session is invalidated at once** (HMAC verification
      fails); all browsers redirect to `/login`. This is the only
      force-logout mechanism — there is no session store.

Keep old secrets out of shell history where practical (`read -s`, a
secrets manager, or an editor buffer cleared afterward).

### Backend Production

```bash
cd apps/api

# Set environment
export ENVIRONMENT=production
export DEBUG=false
export CORS_ORIGINS=https://your-domain.com

# Run with production server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend Production

```bash
cd apps/web

# Set server-side BFF env vars (see .env.example) — API_BASE_URL should be
# the API's private origin (e.g. http://127.0.0.1:8000); API_AUTH_TOKEN must
# match the API; BFF_ALLOWED_ORIGINS must be your HTTPS origin(s).
# No NEXT_PUBLIC_* variables exist — nothing is baked into the bundle.

# Build (no secrets needed at build time)
npm run build

# Start behind TLS
npm start
```

## Database

### Backup

```bash
# Full backup
pg_dump -U opportunityos -d opportunityos > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
pg_dump -U opportunityos -d opportunityos | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore

```bash
# From SQL file
psql -U opportunityos -d opportunityos < backup.sql

# From compressed
gunzip -c backup.sql.gz | psql -U opportunityos -d opportunityos
```

### Migrations

```bash
cd apps/api

# Check current migration
alembic current

# Apply pending migrations
alembic upgrade head

# Create a new migration (if schema changes)
alembic revision --autogenerate -m "description"
```

**Important:** Always run `alembic upgrade head` before starting the application.

## Automation Scheduler

The scheduler performs **internal opportunity intelligence only** — it discovers, normalizes, deduplicates, scores, plans, generates actions, and syncs notifications. It does **NOT** send emails, submit applications, approve outreach, or perform any external actions.

### Configuration

| Variable | Default | Description |
|---|---|---|
| `AUTOMATION_ENABLED` | `false` | Enable the scheduler |
| `AUTOMATION_SCHEDULER_INTERVAL_MINUTES` | `60` | Minutes between intelligence cycles |
| `AUTOMATION_DISCOVERY_ENABLED` | `true` | Run source discovery |
| `AUTOMATION_MATCHING_ENABLED` | `true` | Run deterministic matching |
| `AUTOMATION_AI_INSIGHTS_ENABLED` | `false` | Generate AI insights (requires key) |
| `AUTOMATION_OUTREACH_DRAFTS_ENABLED` | `false` | Generate outreach drafts |
| `AUTOMATION_FOLLOWUP_PROCESSING_ENABLED` | `true` | Mark due follow-ups |
| `AUTOMATION_SOURCES` | `remotive,arbeitnow,himalayas` | Comma-separated source names |
| `AUTOMATION_MIN_MATCH_SCORE` | `60` | Minimum score for high-match counting |
| `AUTOMATION_MAX_OPPORTUNITIES_PER_RUN` | `500` | Max opportunities to process |
| `AUTOMATION_DRY_RUN` | `false` | Dry-run mode for the next run |

### Enabling in Production

```bash
# In your .env or environment:
AUTOMATION_ENABLED=true
AUTOMATION_SCHEDULER_INTERVAL_MINUTES=60
```

### Intelligence Pipeline

Each cycle runs in this order:
1. **Discovery** — fetch from configured source adapters
2. **Matching** — score un-scored opportunities
3. **Planning** — classify into planning horizons
4. **Follow-ups** — mark due follow-ups
5. **Actions** — generate action items
6. **Notifications** — sync attention notifications

### Manual Run

```bash
# Trigger manually
POST /automation/run

# Dry run (no DB mutations)
POST /automation/run {"dry_run": true}

# Single source
POST /automation/run {"source": "remotive"}
```

### Status

```bash
GET /automation/status
GET /automation/config
```

### Safety

- Scheduler only runs when explicitly enabled (`AUTOMATION_ENABLED=true`)
- Does **NOT** send emails or messages
- Does **NOT** submit applications
- Does **NOT** approve outreach drafts
- Does **NOT** bypass any approval workflow
- Idempotent — repeated runs don't create duplicates
- Overlap protection prevents concurrent cycles
- One source failure doesn't stop other sources

## Health Checks

| Endpoint | Purpose | Expected |
|---|---|---|
| `GET /health` | Liveness — is the process running? | `{"status": "ok"}` |
| `GET /health/ready` | Readiness — can it reach the database? | `{"status": "ready"}` |

Use `/health/ready` for load balancer health checks.

## Troubleshooting

### Database connection refused

- Ensure PostgreSQL is running: `docker compose ps`
- Check `DATABASE_URL` in `.env`
- Verify credentials match PostgreSQL configuration

### Migration errors

```bash
alembic current   # Check current migration
alembic heads     # Check expected head
alembic history   # See migration chain
```

### Port already in use

```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000
```

### AI features not working

AI is optional. When `AI_API_KEY` is empty:
- Deterministic matching still works
- Outreach falls back to template drafts
- All other features function normally

### Email not sending

Email is optional. When `EMAIL_HOST` is empty:
- Drafts remain in READY_TO_SEND status
- The send endpoint returns a clear error
- All other features function normally

## Architecture

```
Browser ⇄ Next.js (BFF: /api/bff allowlist proxy + session cookies) ⇄ FastAPI ⇄ PostgreSQL
                                                          ↑
                                                Alembic (migrations)
```

- **PostgreSQL** is the single source of truth
- The **BFF is the only client of FastAPI**; the browser only ever holds an
  HttpOnly session cookie
- **Excel exports** are derived views, not backups
- **Migrations** manage schema changes safely
- **No microservices** — single monorepo deployment

## Production Deployment Checklist

Ordered pre-deploy gate — every step was executed and verified on the
October 2026 hardening pass; re-run the same commands before any real
deployment. Nothing here deploys anything; it only verifies readiness.

### 1. Backend verification

```bash
cd apps/api
.venv/Scripts/python.exe -m pytest -q          # expect: 1232 passed
```

The suite runs against a **dedicated test database** (`opportunityos_test`)
that `tests/conftest.py` creates, wipes and re-migrates on every run. It
never touches the development database — if the isolation guard trips,
fix the guard's precondition (a fresh `DATABASE_URL` pointing at dev)
rather than bypassing it.

### 2. Frontend verification

```bash
cd apps/web
npm test                # vitest
npx eslint .            # zero errors
npx tsc --noEmit        # zero type errors
npm run build           # production build succeeds
npm audit               # no high/critical advisories
```

### 3. Bundle secret scan

No secret **value** may appear in any built client file. Grep for the
actual values from your env files (names alone are safe — UI help text
legitimately mentions `BFF_LOGIN_TOKEN` by name):

```bash
cd apps/web && node -e "
const fs=require('fs'),path=require('path');
function walk(d,out=[]){for(const f of fs.readdirSync(d,{withFileTypes:true})){const p=path.join(d,f.name);f.isDirectory()?walk(p,out):/\\.(js|css|html|txt|json)$/.test(f.name)&&out.push(p);}return out;}
const files=walk('.next/static');
const vals=[];
for(const ef of ['../api/.env','.env.local']){try{for(const line of fs.readFileSync(ef,'utf8').split(/\\r?\\n/)){const m=line.match(/^([A-Z_]*(TOKEN|SECRET))=(\\S+)/);if(m&&m[3].length>=8)vals.push(m[3]);}}catch(e){}}
let hits=0;
for(const f of files){const c=fs.readFileSync(f,'utf8');for(const v of vals){if(c.includes(v)){hits++;console.log('LEAK in',f);}}}
console.log('Scanned',files.length,'client files for',vals.length,'secret values — matches:',hits);
"
# expect: matches: 0 (values are never printed, only leak locations)
```

There are no `NEXT_PUBLIC_*` secrets by design; this check guards against
regressions that inline server-only values.

### 4. Live end-to-end workflow

```bash
# Both servers running (uvicorn :8000, next start :3000), then:
apps/api/.venv/Scripts/python.exe docs/evidence/workflow/live_workflow_test.py
# expect: 62 passed, 0 failed
```

Drives the real stack over HTTP: session login + cookie flags, live
external discovery with dedup on re-run, deterministic scoring, planning,
outreach lifecycle, automation run history, action generation
idempotency, status updates, and 401 on forged sessions.

### 5. Infrastructure

- [ ] PostgreSQL provisioned; `DATABASE_URL` points at it; TLS enforced
      for remote connections
- [ ] `alembic upgrade head` run against the production database
      (`alembic current` shows the head revision)
- [ ] Database backup job scheduled (`pg_dump`); a restore has been
      **tested** at least once
- [ ] Reverse proxy terminates TLS; HSTS enabled

### 6. Secrets and environment

- [ ] `API_AUTH_TOKEN` — 32+ char random value, set in **both**
      `apps/api/.env` and `apps/web/.env.local`
- [ ] `BFF_LOGIN_TOKEN` — independent random value (≠ `API_AUTH_TOKEN`)
- [ ] `SESSION_SECRET` — 32+ char random value
- [ ] `ENVIRONMENT=production`, `DEBUG=false`
- [ ] `CORS_ORIGINS` = frontend origin only
- [ ] `BFF_ALLOWED_ORIGINS` = HTTPS origin(s) only
- [ ] `API_BASE_URL` = API's private origin (not browser-reachable)
- [ ] No secret committed to git (`git status` clean of `.env` files)

### 7. Post-deploy smoke test

- [ ] `GET /health` → `200`, `GET /health/ready` → `200`
- [ ] `/docs`, `/redoc`, `/openapi.json` → `404` (disabled in production)
- [ ] Unauthenticated `GET /api/bff/opportunities` → `401`
- [ ] Sign in at `/login`; session cookie is `HttpOnly`, `SameSite=Lax`,
      `Secure`
- [ ] Forged/expired cookie → `401`
- [ ] Full app flow in browser: overview loads, opportunities list,
      automation run completes, outreach drafts generate
- [ ] Browser console: no errors; no token strings in any network
      response bodies

### 8. Ongoing operations

- [ ] Scheduler enabled only when wanted (`AUTOMATION_ENABLED=true`);
      the pipeline is internal-only — it never sends email or submits
      applications
- [ ] `npm audit` + `pip audit` on a regular cadence
- [ ] Secret rotation runbook above rehearsed once

If any step cannot be verified, treat the deployment as **not ready** —
every step above was executable on a clean checkout during the hardening
pass.
