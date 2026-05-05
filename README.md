# AI SDR Agent

Single-tenant B2B tool for cold outreach: CSV/parser leads, **Anthropic Claude** for copy, **SMTP** outbound, **IMAP** inbound with reply classification and lead status updates.

**Keys:** bring **your own** API keys and mail credentials (see `.env.example`). Never commit real secrets to git.

**Use & responsibility.** This tool helps you **draft and send** outreach email; it is **not legal or compliance advice**. **Commercial email and prospecting are regulated** in many jurisdictions (consent, opt-out, identification of sender, etc.). **You** choose lists, copy, and SMTP accounts — **you are responsible** for lawful use and for damages arising from misuse. The authors and contributors are **not liable** for deliverability, spam classification, or regulatory outcomes.

## Repository layout

| Path | Contents |
|------|-----------|
| `backend/` | FastAPI app (`app/main.py`, `app/application.py`, `app/routers/`, `app/worker/`, `requirements.txt`). Run uvicorn from here; venv lives at `backend/.venv`. |
| `frontend/` | Next.js 14 app (`app/`, `components/`, `messages/`). |
| `tests/` | Pytest suite (root `pytest.ini`). |
| `scripts/` | `dev.sh` (full stack), `run-tests.sh`, `wait-for-postgres.sh`. |
| `docker-compose.yml` | Postgres service for local dev. |
| `LICENSE` | MIT (see **License** below). |
| `package.json` | Root scripts: `npm run dev` → `scripts/dev.sh`; `db:*` → compose helpers. Optional `Makefile` wraps the same. |

## Stack

| Layer | Technologies |
|------|--------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy async, Pydantic |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind |
| Database | PostgreSQL (Docker) |
| AI | Anthropic Messages API (`ANTHROPIC_MODEL`, see `.env.example`) |

## Quick start

1. **PostgreSQL** — from repo root: `docker compose up -d db` or `npm run db:up` (or use your own Postgres).
2. **Repo root** — once: `npm install` (installs root tooling such as `concurrently`; `scripts/dev.sh` will install backend venv and frontend deps when needed).
3. **Backend env** — copy root template: `cp .env.example backend/.env` and fill secrets (or let `scripts/dev.sh` create `backend/.env` from `.env.example` on first run).
4. **Backend Python deps & Playwright** — `scripts/dev.sh` creates `backend/.venv` and runs `pip install`; for the Maps parser run once: `backend/.venv/bin/python -m playwright install chromium`.
5. **Frontend** — `cd frontend && npm install` if you are not using `npm run dev` from root; optional `cp .env.example .env.local`.
6. **Run everything** — from repo root: `npm run dev` (`scripts/dev.sh`: Docker DB → wait for Postgres → uvicorn on `:8000` + Next on `:3000`).

Manual mode: terminal 1 — `cd backend && .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`; terminal 2 — `npm run dev` in `frontend`.

## Environment variables

See **`.env.example`** at the repo root (copied to `backend/.env` for the API). Frontend optional vars are in **`frontend/.env.example`**.

| Group | Purpose |
|--------|---------|
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REMOTE_I18N` | Frontend API URL; optional remote i18n fallback |
| `DATABASE_URL`, `JWT_*`, `CORS_ORIGINS` | API and admin JWT auth |
| `INITIAL_ADMIN_*` | First admin bootstrap |
| `ANTHROPIC_*` | Outbound generation and inbound classification |
| `SMTP_*`, `OUTREACH_DRY_RUN` | Outbound mail (`OUTREACH_DRY_RUN` skips SMTP, still logs) |
| `WORKER_*` | Outreach worker poll interval and batch size |
| `IMAP_*` | Inbound mailbox polling |

Do not commit real secrets; only `.env.example` templates belong in git.

## What it does

- **Admin UI** — login, `/dashboard/campaigns` (prompts, throttle, assigned leads), `/dashboard/leads` (CSV import, Maps parser, bulk assign). Locale EN/RU in `frontend/messages/`.
- **Campaigns & leads** — REST CRUD for campaigns; global lead pool; bulk assign to a campaign. **If a campaign is _Active_ and you attach new leads** (bulk assign or POST lead under campaign), it switches to **Paused** until you press Play again — avoids outreach ignoring freshly added contacts in the queue. **Draft** and **Paused** campaign statuses are unchanged by assign.
- **Outbound worker** — picks `new` leads under `active` campaigns (daily cap + random delay between sends), Claude → SMTP → `EmailInteraction`, lead → `contacted`. Requires `ANTHROPIC_API_KEY`.
- **Inbound worker** — IMAP polling, match sender to lead, classify reply, update status and store inbound interaction.
- **Maps parser** — `POST /api/parser/run` with `{ "location", "keyword", "limit" }` returns immediately; Playwright + optional Claude fills `pain_point` and scrapes emails; leads saved with `campaign_id` null and `source="parser"`.

On API startup, Postgres gets lightweight DDL patches when needed (`backend/app/application.py`). For old DBs migrated manually, ensure `leads.source` and nullable `campaign_id` exist.

## Background workers

Started with FastAPI: **outreach** (`backend/app/worker/outreach_worker.py`) and **imap** (`backend/app/worker/imap_worker.py`). If keys or SMTP/IMAP are missing, workers idle or skip steps — check logs.

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

## Documentation habit (contributors & AI assistants)

After **substantial** changes (new behavior, env vars, workers, endpoints, or UI flows), update **`README.md`** and, when needed, **`.env.example`** and **`frontend/.env.example`**.

---

## Code health (honest snapshot)

**Strengths:** clear split **FastAPI backend / Next.js frontend**, async SQLAlchemy, background workers for outbound and inbound mail, pytest with **in-memory SQLite** and mocks (no real SMTP/IMAP/Anthropic in unit paths), Docker Postgres for local dev, EN/RU UI via JSON messages.

**Watch-outs (ideas for improvement, not blockers):**

- Outreach picks **one global FIFO** of `new` leads across active campaigns — fair **round-robin per campaign** or explicit queues could reduce starvation.
- **RBAC / multi-tenant** beyond a single admin JWT are out of scope today.
- **Observability** could grow (structured logs, metrics, dead-letter for failed sends).
- Parser + Playwright path is **environment-sensitive** (browser install, Maps DOM changes).
- Inbound matching is primarily **by sender email**; alias/thread edge cases may need tuning.

---

## License

This project is **open source** and released under the **[MIT License](LICENSE)**.

The stack builds on **free / open-source** components (Python, FastAPI, Next.js, SQLAlchemy, and others — see `backend/requirements.txt` and `frontend/package.json`). **Anthropic**, **SMTP**, and **IMAP** providers are **third-party services**: you supply keys and credentials; **usage and billing are between you and each provider** under their terms. **No production secrets are shipped** in this repository.

**Tooling:** parts of the codebase were drafted or refactored with **[Cursor](https://cursor.com)** (AI-assisted editing). That does not change licensing: this repo stays MIT; upstream libraries remain under their own licenses.

---

## Say thanks (optional)

If the project saved you time, tips are welcome on **TRC20** (e.g. USDT on Tron). Copy the address from the block below — on **github.com**, hover the code block and use the **copy** icon to avoid typos.

```
TD2q5quUqLDqM3oCzHuWt1ZCjRvkE72KrB
```

---

## Ideas & custom work

Improvements, integrations, or adapting the stack to your workflow — same contact style as [finance_analyzer](https://github.com/mk-projects-dev/finance_analyzer): **[Telegram @fogored](https://t.me/fogored)** or **[mark77793@gmail.com](mailto:mark77793@gmail.com)** — describe what you need.
