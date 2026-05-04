"""Общие фикстуры: in-memory SQLite, ASGI-клиент без lifespan (без фоновых воркеров)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# --- окружение до импорта приложения ---
_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-must-be-at-least-32-bytes-long")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("CORS_ORIGINS", "http://test")
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from app.application import create_app  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, async_session_factory, engine  # noqa: E402

get_settings.cache_clear()

app = create_app(
    start_background_workers=False,
    dispose_engine_on_shutdown=False,
)


@pytest_asyncio.fixture(autouse=True)
async def reset_db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
