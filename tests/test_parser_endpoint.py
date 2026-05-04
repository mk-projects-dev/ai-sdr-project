from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.auth import create_access_token, hash_password
from app.database import async_session_factory
from app.models import Admin, Campaign, CampaignStatus


@pytest.mark.asyncio
async def test_parser_run_accepts_and_schedules_mocked_job(
    client: AsyncClient,
    mocker: pytest.MockFixture,
) -> None:
    mock_job = mocker.patch(
        "app.routers.parser.run_maps_parser_job",
        new_callable=AsyncMock,
    )

    async with async_session_factory() as s:
        admin = Admin(
            email="parser@test.dev",
            hashed_password=hash_password("x"),
        )
        s.add(admin)
        campaign = Campaign(
            name="C",
            system_prompt="S",
            first_email_rules="F",
            follow_up_rules="U",
            status=CampaignStatus.draft,
        )
        s.add(campaign)
        await s.commit()
        await s.refresh(admin)
        await s.refresh(campaign)
        token = create_access_token(admin.id)
        cid = str(campaign.id)

    r = await client.post(
        "/api/parser/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "campaign_id": cid,
            "location": "Киев",
            "keyword": "стоматология",
            "limit": 5,
        },
    )
    assert r.status_code == 200
    assert r.json() == {"status": "started"}

    mock_job.assert_awaited_once()
    args = mock_job.call_args[0]
    assert args[1] == "Киев"
    assert args[2] == "стоматология"
    assert args[3] == 5


@pytest.mark.asyncio
async def test_parser_run_404_unknown_campaign(client: AsyncClient) -> None:
    async with async_session_factory() as s:
        admin = Admin(
            email="a2@test.dev",
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
            "campaign_id": str(uuid4()),
            "location": "X",
            "keyword": "Y",
            "limit": 1,
        },
    )
    assert r.status_code == 404
