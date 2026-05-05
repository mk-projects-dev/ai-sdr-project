# AI SDR Agent

Single-tenant B2B tool for cold outreach: CSV/parser leads, **Anthropic Claude** for copy, **SMTP** outbound, **IMAP** inbound with reply classification and lead status updates.

## Stack

| Layer | Technologies |
|------|--------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy async, Pydantic |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind |
| Database | PostgreSQL (Docker) |
| AI | Anthropic Messages API (`ANTHROPIC_MODEL`, see `.env.example`) |

## Quick start

1. **PostgreSQL** — from repo root: `docker compose up -d db` (or your own Postgres).
2. **Repo root** — once: `npm install` (runs frontend/backend via `npm run dev`).
3. **Backend** — `cd backend`:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python -m playwright install chromium   # for Maps parser
   cp ../.env.example .env && edit secrets
   ```
4. **Frontend** — `cd frontend && npm install`; optional `cp .env.example .env.local`.
5. **Run** — from repo root: `npm run dev` (uses `scripts/dev.sh`: DB wait + uvicorn + Next).

Manual: terminal 1 — uvicorn in `backend`; terminal 2 — `npm run dev` in `frontend`.

## Environment variables

See **`.env.example`** at the repo root. Main groups:

| Group | Purpose |
|--------|---------|
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REMOTE_I18N` | Frontend API URL; optional remote i18n fallback |
| `DATABASE_URL`, `JWT_*`, `CORS_ORIGINS` | API and admin JWT auth |
| `INITIAL_ADMIN_*` | First admin bootstrap |
| `ANTHROPIC_*` | Outbound generation and inbound classification |
| `SMTP_*`, `OUTREACH_DRY_RUN` | Outbound mail (`OUTREACH_DRY_RUN` skips SMTP, still logs) |
| `WORKER_*` | Outreach worker poll interval and batch size |
| `IMAP_*` | Inbound mailbox polling |

Do not commit secrets.

## What it does

- **Admin UI** — login, `/dashboard/campaigns` (prompts, throttle, assigned leads), `/dashboard/leads` (CSV import, Maps parser, bulk assign). Locale EN/RU in `frontend/messages/`.
- **Campaigns & leads** — REST CRUD for campaigns; global lead pool; bulk assign to a campaign. **If a campaign is _Active_ and you attach new leads** (bulk assign or POST lead under campaign), it switches to **Paused** until you press Play again — avoids outreach ignoring freshly added contacts in the queue. **Draft** and **Paused** campaign statuses are unchanged by assign.
- **Outbound worker** — picks `new` leads under `active` campaigns (daily cap + random delay between sends), Claude → SMTP → `EmailInteraction`, lead → `contacted`. Requires `ANTHROPIC_API_KEY`.
- **Inbound worker** — IMAP polling, match sender to lead, classify reply, update status and store inbound interaction.
- **Maps parser** — `POST /api/parser/run` with `{ "location", "keyword", "limit" }` returns immediately; Playwright + optional Claude fills `pain_point` and scrapes emails; leads saved with `campaign_id` null and `source="parser"`.

On API startup, Postgres gets lightweight DDL patches when needed (see `app/application.py`). For old DBs only: ensure `leads.source` and nullable `campaign_id` exist if you migrated manually.

## Background workers

Started with FastAPI: **outreach** (`app/worker/outreach_worker.py`) and **imap** (`app/worker/imap_worker.py`). If keys or SMTP/IMAP are missing, workers idle or skip steps — check logs.

## Tests

From **repository root** (where `pytest.ini` and `tests/` live):

```bash
bash scripts/run-tests.sh
```

Or: `pip install -r backend/requirements.txt -r requirements-dev.txt && python3 -m pytest`.

Playwright: if Chromium missing, run `python -m playwright install chromium` inside backend venv.

Tests use in-memory SQLite and mocks; workers are off (`create_app(start_background_workers=False)`).

## API

Swagger: `http://127.0.0.1:8000/docs` when the backend is running.

---

When behavior or env vars change, update this file and `.env.example` (see `.cursor/rules/readme-maintenance.mdc`).
