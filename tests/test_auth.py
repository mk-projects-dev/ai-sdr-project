from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.auth import hash_password
from app.database import async_session_factory
from app.models import Admin


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    async with async_session_factory() as s:
        s.add(
            Admin(
                email="admin@test.dev",
                hashed_password=hash_password("correct-password"),
            )
        )
        await s.commit()

    r = await client.post(
        "/api/login",
        json={"email": "admin@test.dev", "password": "correct-password"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("access_token")
    assert data.get("token_type") == "bearer"


@pytest.mark.asyncio
async def test_login_failure_wrong_password(client: AsyncClient) -> None:
    async with async_session_factory() as s:
        s.add(
            Admin(
                email="who@test.dev",
                hashed_password=hash_password("secret"),
            )
        )
        await s.commit()

    r = await client.post(
        "/api/login",
        json={"email": "who@test.dev", "password": "wrong-password"},
    )
    assert r.status_code == 401
