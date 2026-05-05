from __future__ import annotations

from unittest.mock import MagicMock

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
        new_callable=MagicMock,
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
    assert r.json() == {"status": "started"}

    mock_job.assert_called_once_with("Киев", "стоматология", 5)
