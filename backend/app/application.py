"""Сборка FastAPI-приложения (прод и тесты с разным lifespan)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — register ORM metadata
from app.bootstrap import ensure_initial_admin
from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, campaigns, health, leads, parser
from app.worker.imap_worker import imap_reply_worker_loop
from app.worker.outreach_worker import outreach_worker_loop


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
