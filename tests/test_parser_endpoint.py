from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.auth import create_access_token, hash_password
from app.database import async_session_factory
from app.models import Admin


@pytest.mark.asyncio
async def test_parser_run_accepts_and_schedules_mocked_job(
    client: AsyncClient,
    mocker: pytest.MockFixture,
) -> None:
    mock_job = mocker.patch(
        "app.routers.parser.run_maps_parser_job",
        new_callable=AsyncMock,
        return_value=0,
    )

    async with async_session_factory() as s:
        admin = Admin(
            email="parser@test.dev",
            hashed_password=hash_password("x"),
        )
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        token = create_access_token(admin.id)

    r = await client.post(
        "/api/parser/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "location": "Киев",
            "keyword": "стоматология",
            "limit": 5,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "started"
    assert isinstance(body.get("started_at"), str) and body["started_at"]

    mock_job.assert_called_once_with("Киев", "стоматология", 5)


@pytest.mark.asyncio
async def test_parser_status_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/parser/status")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_parser_status_ok_when_idle(client: AsyncClient) -> None:
    async with async_session_factory() as s:
        admin = Admin(
            email="parser-status@test.dev",
            hashed_password=hash_password("x"),
        )
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        token = create_access_token(admin.id)

    r = await client.get(
        "/api/parser/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["busy"] is False
    assert data["last_created_count"] == 0
