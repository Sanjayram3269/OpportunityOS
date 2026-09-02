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

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd apps/web
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev
```

### 4. Verify

- API health: http://localhost:8000/health
- API readiness: http://localhost:8000/health/ready
- API docs (dev only): http://localhost:8000/docs
- Frontend: http://localhost:3000

## Production Deployment

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection URL |
| `ENVIRONMENT` | ✅ | Set to `production` |
| `DEBUG` | ✅ | Set to `false` |
| `CORS_ORIGINS` | ✅ | Your frontend domain(s) |
| `AI_API_KEY` | Optional | AI provider key |
| `EMAIL_HOST` | Optional | SMTP server for email delivery |

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

# Set API URL
echo "NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.com" > .env.local

# Build
npm run build

# Start
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
PostgreSQL ← SQLAlchemy ← FastAPI ← Next.js
                ↑
          Alembic (migrations)
```

- **PostgreSQL** is the single source of truth
- **Excel exports** are derived views, not backups
- **Migrations** manage schema changes safely
- **No microservices** — single monorepo deployment
