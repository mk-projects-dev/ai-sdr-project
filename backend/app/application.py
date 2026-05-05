"""Сборка FastAPI-приложения (прод и тесты с разным lifespan)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401 — register ORM metadata
from app.bootstrap import ensure_initial_admin
from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, campaigns, health, leads, parser
from app.worker.imap_worker import imap_reply_worker_loop
from app.worker.outreach_worker import outreach_worker_loop


async def _ensure_postgres_lead_source_column(conn) -> None:
    """create_all не добавляет новые колонки в уже существующие таблицы — только ALTER."""
    if conn.engine.dialect.name != "postgresql":
        return
    await conn.execute(
        text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS source VARCHAR(64)")
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_leads_source ON leads (source)")
    )


async def _ensure_campaign_send_throttle_columns(conn) -> None:
    """Лимит писем/день и пауза между отправками (create_all не добавляет колонки в старые таблицы)."""
    dialect = conn.engine.dialect.name
    if dialect == "postgresql":
        await conn.execute(
            text(
                "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS max_emails_per_day "
                "INTEGER NOT NULL DEFAULT 50"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS send_delay_min_seconds "
                "INTEGER NOT NULL DEFAULT 300"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS send_delay_max_seconds "
                "INTEGER NOT NULL DEFAULT 1200"
            )
        )
        return
    if dialect == "sqlite":

        def _add_sqlite_columns(sync_conn) -> None:
            from sqlalchemy import inspect

            insp = inspect(sync_conn)
            cols = {c["name"] for c in insp.get_columns("campaigns")}
            if "max_emails_per_day" not in cols:
                sync_conn.execute(
                    text(
                        "ALTER TABLE campaigns ADD COLUMN max_emails_per_day "
                        "INTEGER NOT NULL DEFAULT 50"
                    )
                )
            if "send_delay_min_seconds" not in cols:
                sync_conn.execute(
                    text(
                        "ALTER TABLE campaigns ADD COLUMN send_delay_min_seconds "
                        "INTEGER NOT NULL DEFAULT 300"
                    )
                )
            if "send_delay_max_seconds" not in cols:
                sync_conn.execute(
                    text(
                        "ALTER TABLE campaigns ADD COLUMN send_delay_max_seconds "
                        "INTEGER NOT NULL DEFAULT 1200"
                    )
                )

        await conn.run_sync(_add_sqlite_columns)


async def _ensure_postgres_lead_campaign_optional(conn) -> None:
    """Лиды без кампании: campaign_id NULL, при удалении кампании — SET NULL."""
    if conn.engine.dialect.name != "postgresql":
        return
    await conn.execute(
        text("ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_campaign_id_fkey")
    )
    await conn.execute(
        text("ALTER TABLE leads ALTER COLUMN campaign_id DROP NOT NULL")
    )
    await conn.execute(
        text(
            "ALTER TABLE leads ADD CONSTRAINT leads_campaign_id_fkey "
            "FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL"
        )
    )


def create_app(
    *,
    start_background_workers: bool = True,
    dispose_engine_on_shutdown: bool = True,
) -> FastAPI:
    """Если start_background_workers=False (pytest), воркеры outreach/IMAP не запускаются.
    В тестах dispose_engine_on_shutdown=False, чтобы пул SQLite не закрывался между кейсами."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _ensure_postgres_lead_source_column(conn)
            await _ensure_postgres_lead_campaign_optional(conn)
            await _ensure_campaign_send_throttle_columns(conn)
        await ensure_initial_admin()
        outreach_task = None
        imap_task = None
        if start_background_workers:
            outreach_task = asyncio.create_task(outreach_worker_loop())
            imap_task = asyncio.create_task(imap_reply_worker_loop())
        yield
        for t in (outreach_task, imap_task):
            if t is not None:
                t.cancel()
        for t in (outreach_task, imap_task):
            if t is None:
                continue
            try:
                await t
            except asyncio.CancelledError:
                pass
        if dispose_engine_on_shutdown:
            await engine.dispose()

    app = FastAPI(title="AI SDR Agent", lifespan=lifespan)

    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(campaigns.router, prefix="/api")
    app.include_router(leads.router, prefix="/api")
    app.include_router(parser.router, prefix="/api")

    return app
