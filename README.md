# AI SDR Agent

Single-tenant B2B app for cold outreach: lead import (CSV), email generation with **Anthropic Claude**, delivery via **SMTP**, inbound replies over **IMAP** with intent classification and lead status updates.

## Stack

| Layer | Technologies |
|------|--------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy async, Pydantic |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui |
| Database | PostgreSQL (Docker) |
| AI | Anthropic SDK (`ANTHROPIC_MODEL`, defaults from `.env`) |

## Quick start

1. **PostgreSQL** — from the repo root: `docker compose up -d db` (or use your own Postgres).
2. **Repo root** — once: `npm install` (orchestrates `npm run dev`).
3. **Backend** — `cd backend`, virtualenv and dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python -m playwright install chromium   # for POST /api/parser/run (Google Maps)
   cp ../.env.example .env     # if needed; fill in secrets
   ```
4. **Frontend** — `cd frontend && npm install`; optionally `cp .env.example .env.local`.
5. **Run everything** (from repo root):
   ```bash
   npm run dev
   ```
   `scripts/dev.sh` starts the DB, waits for Postgres, then runs FastAPI and Next.js in parallel (see `package.json`).

Manual mode: terminal 1 — `uvicorn` in `backend`; terminal 2 — `npm run dev` in `frontend`.

## Environment variables

See **`.env.example`** at the repo root for the full list. Main groups:

| Group | Purpose |
|--------|---------|
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REMOTE_I18N` | Frontend → API; optional toggle for online i18n fallback |
| `DATABASE_URL`, `JWT_*`, `CORS_ORIGINS` | API and admin auth |
| `INITIAL_ADMIN_*` | Bootstrap first administrator |
| `ANTHROPIC_*` | Email generation and inbound classification |
| `SMTP_*`, `OUTREACH_DRY_RUN` | Outbound mail (dry-run skips SMTP but still writes DB) |
| `WORKER_*` | **Outreach** worker poll interval and batch size |
| `IMAP_*` | Inbound replies (phase 5): mailbox, SSL, poll interval |

Do not commit secrets; use `.env.example` only as a template.

## Architecture by phase

1. **Skeleton** — Docker Compose Postgres, JWT `/api/login`, `/api/health`, ORM models.
2. **Frontend** — login, dashboard shell, `NEXT_PUBLIC_API_URL`.
3. **Campaigns & leads** — CRUD `/api/campaigns`; global lead pool `GET /api/leads`, `POST /api/leads/import`, `POST /api/leads/bulk-assign`; campaign-scoped lists `GET /api/campaigns/{id}/leads`. UI: `/dashboard/campaigns` (prompts + assigned leads per campaign), **`/dashboard/leads`** (CSV/parser + bulk assign). **UI localization** — `frontend/messages/en.json` and `ru.json` (**English is default**), switcher in header/sidebar, locale in `localStorage` (`aisdr_locale`). Missing Russian keys fall back to English; with online mode enabled (not `NEXT_PUBLIC_REMOTE_I18N=false`), missing phrases can be filled via the free MyMemory API with cache in `sessionStorage`. Full-screen **`PageLoader`** blocks interaction during initial data fetch, login/home redirect, or heavy saves until state is ready.
4. **Outbound** — background worker: leads `new` + campaign `active` → Claude → SMTP → outbound `EmailInteraction`, lead status `contacted`.
5. **Inbound** — background IMAP worker: unseen mail → match lead by sender → Claude classifies reply (`interested` / `replied` / `rejected`) → inbound `EmailInteraction` and lead status update; dedupe by `Message-ID` in `imap_processed_messages`.
6. **Google Maps parser** — `POST /api/parser/run` (JWT): body `{ "location", "keyword", "limit" }` (no campaign). Returns immediately `{"status":"started"}`; Playwright opens Maps in the background, collects business cards, calls Claude for `pain_point`, tries to scrape email from websites (httpx + BeautifulSoup), saves leads with `campaign_id` unset, `source="parser"`, status `new`. Rows without a found email are skipped. Requires Playwright browsers (`python -m playwright install chromium`) and preferably `ANTHROPIC_API_KEY` (otherwise a fallback pain text is used).

On startup the API applies Postgres-compatible DDL patches when needed (e.g. `leads.source`, nullable `leads.campaign_id` with `ON DELETE SET NULL`). For manual fixes on older DBs you can still run:

`ALTER TABLE leads ADD COLUMN IF NOT EXISTS source VARCHAR(64);`  
`CREATE INDEX IF NOT EXISTS ix_leads_source ON leads (source);`

## Background workers

On FastAPI startup two asyncio tasks run:

- **outreach** (`app/worker/outreach_worker.py`) — outbound queue.
- **imap** (`app/worker/imap_worker.py`) — IMAP polling at `IMAP_POLL_INTERVAL_SECONDS`.

If `ANTHROPIC_API_KEY`, `IMAP_*`, or SMTP are unset (depending on mode), steps are skipped or the worker waits (see logs).

## Automated tests (pytest)

Run `pip`/`pytest` from the **repository root** (where `pytest.ini` and `tests/` live). If your shell is in `backend/`, use `pip install -r requirements.txt` without the `backend/` prefix.

Script from any directory (changes to repo root):

```bash
bash scripts/run-tests.sh
```

Manual run from root:

```bash
cd /path/to/ai-sdr-project
python3 -m pip install -r backend/requirements.txt
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

If you see **`collected 0 items`**, ensure your cwd contains `pytest.ini` and `tests/` is not empty.

If the Maps parser reports **`Executable doesn't exist`** for Chromium: once in `backend` with venv active run **`python -m playwright install chromium`** (preferably outside an IDE sandbox). If logs mention **`cursor-sandbox-cache`**, the app clears `PLAYWRIGHT_BROWSERS_PATH` when starting the parser and uses the default user browser cache; if needed run **`unset PLAYWRIGHT_BROWSERS_PATH`** and restart the API.

Tests use in-memory **SQLite** (`sqlite+aiosqlite:///:memory:`), mock **Anthropic**, **SMTP**, and the parser background job; outreach/IMAP workers **do not** start in the test app (`app.application.create_app`).

## API docs

In development: **Swagger** — `http://127.0.0.1:8000/docs` (with backend running).

---

*When behavior changes, update this file and `.env.example` (see `.cursor/rules/readme-maintenance.mdc`).*
