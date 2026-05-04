from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from app.auth import create_access_token, hash_password
from app.database import async_session_factory
from app.models import Admin


async def _auth_header() -> dict[str, str]:
    async with async_session_factory() as s:
        admin = Admin(
            email="owner@test.dev",
            hashed_password=hash_password("pwd"),
        )
        s.add(admin)
        await s.commit()
        await s.refresh(admin)
        token = create_access_token(admin.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_campaign_and_import_csv_leads(client: AsyncClient) -> None:
    headers = await _auth_header()

    cr = await client.post(
        "/api/campaigns",
        headers=headers,
        json={
            "name": "Test campaign",
            "system_prompt": "You are helpful.",
            "first_email_rules": "Be short.",
            "follow_up_rules": "Follow up weekly.",
            "status": "draft",
        },
    )
    assert cr.status_code == 201
    campaign_id = cr.json()["id"]

    csv_body = "email,company_name\nalice@example.com,AliceCo\nbob@example.com,Bob Ltd\n"
    files = {"file": ("leads.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")}
    ir = await client.post(
        f"/api/campaigns/{campaign_id}/leads/import",
        headers=headers,
        files=files,
    )
    assert ir.status_code == 200
    result = ir.json()
    assert result["created"] == 2
    assert result["skipped"] == 0

    lr = await client.get(
        f"/api/campaigns/{campaign_id}/leads",
        headers=headers,
    )
    assert lr.status_code == 200
    leads = lr.json()
    assert len(leads) == 2
    emails = {row["email"] for row in leads}
    assert emails == {"alice@example.com", "bob@example.com"}
