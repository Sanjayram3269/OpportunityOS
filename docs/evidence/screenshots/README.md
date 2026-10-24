# Screenshots — live application

Captured October 24, 2026 from the running stack
(Next.js BFF :3000 → FastAPI :8000 → PostgreSQL) at 1440×900, signed in
through the real `/login` session flow. All data shown is real data from
the development database (324 ingested live listings); nothing is mocked
or staged.

| File | Page | What it evidences |
|---|---|---|
| `01-overview-dashboard.png` | `/` Command Center | Live counts (324 opportunities, 5 open actions), attention feed with CRITICAL overdue items, Today strip |
| `02-opportunities-ranked.png` | `/opportunities` | Deterministic scores (0–100) on every row, type/status/priority badges, planning horizons (NOW/FUTURE/UNKNOWN), deadlines |
| `03-automation-run-history.png` | `/automation` | Pipeline configuration toggles, safety banner (human approval required), persisted run history with COMPLETED status, durations and per-run counts |
| `04-planning-horizons.png` | `/planning` | Horizon grouping (Now 6 / Upcoming 0 / Summer 2027 0 / Future 10 / Unknown 84), per-card match score, status and due dates |
| `05-outreach-approval-lifecycle.png` | `/outreach` | Draft cards with lifecycle tabs (Drafts/Pending/Approved/Ready/Sent/Rejected), `READY_TO_SEND` state — nothing sends without approval |

## Reproducing

```bash
# Start both servers (see DEPLOY.md Quick Start), then sign in at
# http://localhost:3000/login with BFF_LOGIN_TOKEN and capture at 1440×900.
```

The sign-in token and session cookie are never written to any file in
this directory.
