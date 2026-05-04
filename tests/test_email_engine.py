from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.auth import hash_password
from app.config import get_settings
from app.database import async_session_factory
from app.models import Campaign, CampaignStatus, Lead, LeadStatus
from app.worker.outreach_worker import process_outreach_once


@pytest.mark.asyncio
async def test_outreach_pipeline_updates_lead_and_sends_once(mocker: pytest.MockFixture) -> None:
    gen = mocker.patch(
        "app.worker.outreach_worker.generate_first_outreach_email",
        new_callable=AsyncMock,
        return_value=("Hello subject", "Hello body"),
    )
    send = mocker.patch(
        "app.worker.outreach_worker.send_outreach_email",
        new_callable=AsyncMock,
    )

    get_settings.cache_clear()
    mocker.patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-test-key-for-unit-tests-only"},
        clear=False,
    )
    get_settings.cache_clear()

    async with async_session_factory() as s:
        campaign = Campaign(
            name="Active",
            system_prompt="Sys",
            first_email_rules="Rules",
            follow_up_rules="Follow",
            status=CampaignStatus.active,
        )
        s.add(campaign)
        await s.flush()
        lead = Lead(
            campaign_id=campaign.id,
            email="lead@test.dev",
            company_name="Co",
            pain_point="Pain",
            status=LeadStatus.new,
        )
        s.add(lead)
        await s.commit()

    ok = await process_outreach_once()
    assert ok is True

    gen.assert_awaited_once()
    send.assert_awaited_once()

    async with async_session_factory() as s:
        from sqlalchemy import select

        r = await s.execute(select(Lead).where(Lead.email == "lead@test.dev"))
        updated = r.scalar_one()
        assert updated.status == LeadStatus.contacted
