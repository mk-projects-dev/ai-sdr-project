from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.auth import hash_password
from app.database import async_session_factory
from app.models import Admin, EmailDirection, EmailInteraction, Lead, LeadStatus


@pytest.mark.asyncio
async def test_billing_summary_unauthorized(client: AsyncClient) -> None:
    r = await client.get("/api/billing/summary")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_billing_summary_totals(client: AsyncClient) -> None:
    async with async_session_factory() as s:
        s.add(
            Admin(
                email="bill2@test.dev",
                hashed_password=hash_password("pw"),
            )
        )
        lead = Lead(
            campaign_id=None,
            email="lbill@test.dev",
            status=LeadStatus.new,
        )
        s.add(lead)
        await s.flush()
        s.add(
            EmailInteraction(
                lead_id=lead.id,
                direction=EmailDirection.outbound,
                subject="s",
                body="b",
                ai_intent="first_outreach",
                input_tokens=1000,
                output_tokens=500,
                cost=0.012,
            )
        )
        await s.commit()

    login = await client.post(
        "/api/login",
        json={"email": "bill2@test.dev", "password": "pw"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    r = await client.get(
        "/api/billing/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_input_tokens"] == 1000
    assert data["total_output_tokens"] == 500
    assert abs(float(data["total_cost"]) - 0.012) < 1e-9
