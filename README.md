# AI SDR Agent

Single-tenant B2B-приложение для холодного аутрича: импорт лидов (CSV), генерация писем через **Anthropic Claude**, отправка по **SMTP**, обработка входящих ответов по **IMAP** с классификацией намерения и обновлением статуса лида.

## Стек

| Слой | Технологии |
|------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy async, Pydantic |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui |
| БД | PostgreSQL (Docker) |
| AI | Anthropic SDK (`ANTHROPIC_MODEL`, по умолчанию из `.env`) |

## Быстрый старт

1. **PostgreSQL** — в корне проекта: `docker compose up -d db` (или свой Postgres).
2. **Корень репозитория** — один раз: `npm install` (оркестрация `npm run dev`).
3. **Backend** — `cd backend`, виртуальное окружение и зависимости:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp ../.env.example .env     # при необходимости; заполнить секреты
   ```
4. **Frontend** — `cd frontend && npm install`, при необходимости `cp .env.example .env.local`.
5. **Запуск всего сразу** (из корня репозитория):
   ```bash
   npm run dev
   ```
   Скрипт `scripts/dev.sh` поднимает БД, ждёт Postgres, параллельно стартует FastAPI и Next.js (см. `package.json`).

Ручной режим: терминал 1 — `uvicorn` в `backend`; терминал 2 — `npm run dev` в `frontend`.

## Переменные окружения

Полный список см. **`.env.example`** в корне. Ключевые группы:

| Группа | Назначение |
|--------|------------|
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REMOTE_I18N` | Frontend → API; опционально отключить онлайн-доперевод для i18n |
| `DATABASE_URL`, `JWT_*`, `CORS_ORIGINS` | API и авторизация админа |
| `INITIAL_ADMIN_*` | Bootstrap первого администратора |
| `ANTHROPIC_*` | Генерация писем и классификация входящих |
| `SMTP_*`, `OUTREACH_DRY_RUN` | Исходящая почта (dry-run не шлёт SMTP, но пишет в БД) |
| `WORKER_*` | Частота опроса и размер батча **outreach**-воркера |
| `IMAP_*` | Входящие ответы (Фаза 5): ящик, SSL, интервал опроса |

Секреты не коммитить; для образца использовать только `.env.example`.

## Архитектура по фазам

1. **Скелет** — Docker Compose с Postgres, JWT `/api/login`, `/api/health`, ORM-модели.
2. **Frontend** — логин, layout дашборда, `NEXT_PUBLIC_API_URL`.
3. **Кампании и лиды** — CRUD `/api/campaigns`, `/api/leads`, импорт CSV, UI в `/dashboard/campaigns`; **локализация** UI — `frontend/messages/en.json` и `ru.json` (по умолчанию **английский**), переключатель в шапке/сайдбаре, выбор языка в `localStorage` (`aisdr_locale`). Если для русского нет ключа, показывается английский текст; при включённом онлайн-режиме (не `NEXT_PUBLIC_REMOTE_I18N=false`) отсутствующие фразы можно доперевести через бесплатный API MyMemory с кэшем в `sessionStorage`. Пока идёт первая загрузка данных, редирект с логина / домашней страницы или сохранение/импорт на карточке кампании, поверх UI показывается полноэкранный лоадер (`PageLoader`), чтобы не взаимодействовать с неполным состоянием.
4. **Исходящие** — фоновый воркер: лиды `new` + кампания `active` → Claude → SMTP → `EmailInteraction` outbound, статус лида `contacted`.
5. **Входящие** — фоновый IMAP-воркер: непрочитанные письма → по адресу отправителя ищется лид → Claude классифицирует ответ (`interested` / `replied` / `rejected`) → запись `EmailInteraction` inbound и обновление статуса лида; дедупликация по `Message-ID` в таблице `imap_processed_messages`.

## Фоновые процессы

При старте FastAPI поднимаются две asyncio-задачи:

- **outreach** (`app/worker/outreach_worker.py`) — очередь исходящих.
- **imap** (`app/worker/imap_worker.py`) — опрос IMAP с интервалом `IMAP_POLL_INTERVAL_SECONDS`.

Если не заданы `ANTHROPIC_API_KEY`, `IMAP_*` или SMTP (в зависимости от режима), соответствующие шаги корректно пропускаются или воркер ждёт (см. логи).

## Документация API

В режиме разработки: **Swagger** — `http://127.0.0.1:8000/docs` (при запущенном backend).

---

*При изменении функционала обновляйте этот файл и `.env.example` (см. правило в `.cursor/rules/readme-maintenance.mdc`).*
