# OpportunityOS

<p align="center">
  <strong>Your AI-powered operating system for finding, evaluating, and acting on opportunities.</strong>
  <br />
  <em>One place to discover opportunities, understand their fit, prepare your next move, and manage the entire journey.</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-FastAPI-3776AB?logo=python&logoColor=white" />
  <img alt="Next.js" src="https://img.shields.io/badge/Frontend-Next.js-black?logo=next.js" />
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-Ready-3178C6?logo=typescript&logoColor=white" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white" />
  <img alt="Status" src="https://img.shields.io/badge/Status-Active%20Development-orange" />
</p>

---

## The problem

Opportunities are scattered across job boards, company career pages, research programs, startup communities, referrals, competitions, and personal networks. Keeping track of them is fragmented work: searching, comparing requirements, figuring out who to contact, tailoring materials, remembering follow-ups, and learning which approaches work.

**OpportunityOS turns that fragmented work into one structured, explainable workflow.**

It is being built as a personal opportunity command center—not merely a job scraper or a spreadsheet. The goal is to help a person move from *“I might be interested in this”* to *“I understand it, know why it fits, have a plan, and know what to do next.”*

## Product vision

```text
PROFILE & PREFERENCES
        ↓
DISCOVER → NORMALIZE → DEDUPLICATE
        ↓
MATCH → EXPLAIN → RESEARCH
        ↓
PRIORITIZE → PLAN → PERSONALIZE
        ↓
PREPARE → REVIEW / APPROVE
        ↓
AUTHORIZED ACTION → TRACK
        ↓
FOLLOW UP → ANALYZE → LEARN
```

The intended experience is simple: define what matters to you, let OpportunityOS organize and evaluate relevant opportunities, review its recommendations, and keep every application, conversation, and next action in one place.

## What kinds of opportunities?

OpportunityOS is designed around a broad opportunity model. It should not be limited to a single job board, location, role, or season.

- **Careers:** internships, graduate roles, full-time roles, startups, and product-company positions.
- **Research:** research internships, labs, academic programs, and collaborations.
- **Independent work:** freelance projects, consulting, contracts, and client leads.
- **Growth:** hackathons, fellowships, competitions, communities, and relevant collaborations.
- **Networking:** referrals, hiring-team outreach, founder conversations, and professional follow-ups.

Targeting is intended to be configurable: India-first, city-specific, remote, or worldwide when relevant. Timing can balance immediate opportunities with future cycles such as Summer 2027. A future target should not hide a strong opportunity available now.

## Current capabilities

The repository already contains a substantial working foundation. The list below describes implemented workflow areas; it does **not** imply every future integration or end-term feature is already available.

| Area | Current foundation |
|---|---|
| Opportunity discovery | Pluggable source-adapter architecture, with Remotive, Arbeitnow, and Himalayas adapters |
| Normalization & deduplication | Converts source records into a consistent opportunity model and avoids repeated ingestion |
| Company association | Connects discovered opportunities to company records |
| Matching | Deterministic, explainable match scoring with supporting signals, matched skills, gaps, and concerns |
| Optional AI insights | Structured opportunity insights that complement—not replace—the deterministic matching result |
| Planning | Deadline-aware planning horizons, including Summer 2027 |
| Applications | Application lifecycle, transitions, and chronological timeline events |
| Action Center | Generates prioritized, idempotent actions from the current opportunity workflow |
| Outreach | Drafting and explicit approval states, with configured email delivery paths |
| Follow-ups | Follow-up lifecycle, due handling, and timezone-aware scheduling |
| Campaigns | Groups and organizes opportunities for focused activity |
| Notifications | Persistent attention items, unread state, and idempotent synchronization |
| Automation | Orchestrates discovery, matching, planning, follow-ups, actions, and notifications |
| Run history | Persists automation run status and summary metrics |
| Analytics | Opportunity and application analytics, conversion views, trends, and campaign drill-down |
| Export | Workbook export for portable reporting |
| Operational foundation | FastAPI health/readiness endpoints, structured logging, environment configuration, and PostgreSQL migrations |

### Current source integrations

The current discovery adapters are:

- **Remotive**
- **Arbeitnow**
- **Himalayas**

Other platforms and sources—including LinkedIn, Handshake, and JobStep—must be treated as **planned or access-dependent** until their specific authorized integration path is verified. Listing a platform in the product roadmap does not mean a live connector currently exists.

## Human control is a product principle

OpportunityOS is designed to automate the work around a decision while preserving a clear and auditable boundary around external actions.

**Automate where appropriate:** discovery from supported sources, normalization, deduplication, matching, prioritization, company research from legitimate sources, drafting, reminders, status tracking, and analytics.

**Keep control explicit:** review generated content, approve consequential actions, and use only authorized sending or submission mechanisms. If a platform does not provide permitted access for an action, the product should present a prepared handoff rather than simulate authorization.

The project does not aim to bypass platform restrictions, scrape services without permission, harvest private contact data, or send automated messages through unauthorized browser bots. Credentials and session cookies should never be embedded in source code.

## Architecture

OpportunityOS uses a monorepo structure with a web application, API, and infrastructure configuration.

```text
OpportunityOS/
├── apps/
│   ├── api/       # FastAPI backend, domain services, schemas, migrations and tests
│   └── web/       # Next.js frontend, TypeScript UI and API client
├── infra/
│   └── postgres/  # Local PostgreSQL infrastructure
├── DEPLOY.md      # Deployment and operational guidance
└── README.md
```

### Technology

| Layer | Technology |
|---|---|
| Web application | Next.js, React, TypeScript |
| API | Python, FastAPI, Pydantic |
| Persistence | PostgreSQL |
| ORM & migrations | SQLAlchemy 2.x, Alembic |
| Validation & contracts | Pydantic schemas and typed frontend API models |
| Automation | Application-level orchestrator and scheduler |
| Optional AI | Provider-abstracted structured insights |
| Export | Excel workbook generation |
| Local infrastructure | Docker Compose |

### Architectural principles

1. **PostgreSQL is the source of truth.** Excel is an export/reporting format, not a competing database.
2. **Domain rules stay deterministic where correctness matters.** AI can explain and recommend; it must not secretly override lifecycle states, approvals, verified facts, or permissions.
3. **Source adapters are replaceable.** Each provider should be normalized into canonical domain records rather than creating a separate business system.
4. **Lifecycle changes are explicit and traceable.** Applications, outreach, follow-ups, notifications, and automation runs have structured states.
5. **Idempotency matters.** Repeated ingestion, action generation, and notification synchronization should not create duplicate work.
6. **Failure should be observable.** Operational endpoints, logs, and persistent automation-run summaries support troubleshooting.
7. **Secrets stay out of Git.** Runtime configuration belongs in local environment files or deployment secrets.

## The end-term product

The roadmap is to evolve the current foundation into a personalized opportunity agent with the following capabilities.

### 1. Personal profile and preferences
A canonical profile for education, skills, experience, projects, achievements, GitHub, LinkedIn, portfolio links, resumes, cover-letter material, location, availability, compensation preferences, and target roles. User-provided facts should remain editable and distinguishable from inferred information.

### 2. Opportunity targeting
Configurable priorities for role families, cities, remote/on-site preferences, compensation, work authorization, experience requirements, timing, company stage, and industries. For example, a user can prioritize paid, on-site Chennai opportunities available in December while keeping Summer 2027 as a major long-term goal.

### 3. Company and contact intelligence
Research companies using legitimate public information and authorized sources. Track the source and confidence for facts such as company website, careers page, founders, recruiting channels, and publicly listed contact details. Unknown or unverified information should remain marked as such.

### 4. Application preparation
Recommend the most relevant resume variant, suggest evidence-backed edits, draft a role-specific cover letter, and prepare answers to application questions from the user's real experience. The system must not invent qualifications, employment, achievements, or skills.

### 5. Personalized outreach
Draft distinct, contextual messages for recruiters, hiring managers, founders, or official recruiting email addresses where those contact routes are legitimately available. Track approvals, delivery outcomes, responses, and follow-up tasks.

### 6. Daily attention and mobile access
A concise daily brief showing new matches, urgent deadlines, pending approvals, interviews, and follow-ups. A responsive web experience and eventual installable PWA can make review and notifications useful on a phone.

### 7. Learning from outcomes
Measure which sources, role types, match signals, applications, and outreach patterns lead to replies or interviews. User decisions should inform transparent, adjustable preferences—not an opaque scoring system.

These are **roadmap goals, not claims that all functionality is implemented today**. The roadmap should be delivered in tested, dependency-ordered milestones.

## Development status and roadmap

The project is actively evolving. The near-term sequence is:

1. **Complete repository audit** — verify each workflow, capture known issues, and produce a prioritized gap register.
2. **Personal profile foundation** — establish a canonical, editable source of professional facts and documents.
3. **Preference and targeting engine** — make role, location, compensation, and timing preferences first-class.
4. **Company/contact intelligence** — add source provenance and verification states.
5. **Application and outreach preparation** — connect profile evidence to tailored drafts and human review.
6. **Source integrations** — implement only connectors with a legitimate, supportable access path.
7. **Product-wide UI/UX pass** — consistent typography, navigation, forms, empty/error/loading states, accessible components, and mobile layout.
8. **Production readiness** — deployment, secrets management, backups, observability, and a real-world validation cycle.

Feature status will be updated as milestones are completed and verified. Planned work should not be presented as shipped functionality.

## Local development

### Prerequisites

- Git
- Python compatible with the API project's configuration
- Node.js and npm compatible with the web project's configuration
- Docker Desktop / Docker Compose

### 1. Clone the repository

```bash
git clone https://github.com/Sanjayram3269/OpportunityOS.git
cd OpportunityOS
```

### 2. Start PostgreSQL

Review the Compose configuration under `infra/postgres/`. Create the local environment file required by that Compose configuration, using non-production development values only, then start the service:

```bash
cd infra/postgres
docker compose up -d
```

### 3. Configure and start the API

Create the API environment file using the project's example/configuration guidance. Never commit credentials or production secrets.

From `apps/api`, install the dependencies according to the repository's Python project configuration, apply migrations, and start the development server. The usual local entry point is:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API's health and readiness endpoints are available at `/health` and `/health/ready` once the server is running. Consult `apps/api/` and [DEPLOY.md](DEPLOY.md) for the exact environment and dependency setup.

### 4. Configure and start the web application

Set the web app's local environment variable `NEXT_PUBLIC_API_BASE_URL` to the API base URL, install dependencies from `apps/web`, and run:

```bash
npm install
npm run dev
```

The local web app typically runs at `http://localhost:3000`, and the API at `http://localhost:8000`. Confirm the configured ports and environment values for your machine.

> **Local setup note:** use the committed project configuration as the authority for exact Python versions, scripts, and environment variable requirements. Keep real API keys, SMTP credentials, passwords, personal documents, and tokens in ignored local environment files or a deployment secret store.

## Testing and engineering workflow

OpportunityOS is developed in small vertical milestones:

1. Inspect existing architecture and working tree.
2. Make one coherent, scoped change.
3. Add or update tests for expected behavior and failure cases.
4. Run the relevant API tests, frontend tests, type checks, and migration checks.
5. Review security and authorization boundaries.
6. Record the outcome, commit the verified milestone, and proceed to the next dependency.

A green unit-test suite does not substitute for external API access verification or a real end-to-end run against correctly configured services. Keep these checks distinct in release notes.

## Data and privacy principles

- Store only information required for the intended workflow.
- Keep contact details linked to their source and verification status.
- Treat resumes and other personal documents as sensitive user data.
- Never hard-code credentials, API tokens, SMTP passwords, or session cookies.
- Avoid fabricating company facts, contact details, deadlines, salary, or hiring status.
- Make external actions visible and auditable.
- Respect provider terms, access controls, rate limits, and applicable privacy requirements.
- Prefer free/open-source services where practical; make optional AI providers configurable rather than requiring a specific paid provider.

## Deployment

See **[DEPLOY.md](DEPLOY.md)** for the repository's deployment and operational guidance. Before exposing the application publicly, review authentication and access control, HTTPS termination, database backups, secret handling, rate limiting, document storage, and the deployment's threat model. Do not assume that a single-user local development setup is ready for public multi-user use without these safeguards.

## Contributing

This is an actively developed personal project. Before proposing a change:

- Check the existing service and route patterns before adding parallel logic.
- Reuse canonical models and lifecycle services.
- Keep migration history coherent.
- Add tests for success, validation, idempotency, authorization, and failure behavior where applicable.
- Document whether a capability is implemented, partially implemented, or planned.

## North star

> **OpportunityOS should help turn a broad goal into a prioritized set of real opportunities—and turn each chosen opportunity into a well-prepared, trackable next action.**

Discover intelligently. Decide transparently. Prepare carefully. Act with control. Learn from outcomes.

---

**Repository:** [Sanjayram3269/OpportunityOS](https://github.com/Sanjayram3269/OpportunityOS)  
**Owner:** Sanjayram P.
