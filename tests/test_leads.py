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
async def test_import_csv_global_then_bulk_assign(client: AsyncClient) -> None:
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
        "/api/leads/import",
        headers=headers,
        files=files,
    )
    assert ir.status_code == 200
    result = ir.json()
    assert result["created"] == 2
    assert result["skipped"] == 0

    all_lr = await client.get("/api/leads", headers=headers)
    assert all_lr.status_code == 200
    pool = all_lr.json()
    assert len(pool) == 2
    lead_ids = [row["id"] for row in pool]
    assert {row["email"] for row in pool} == {"alice@example.com", "bob@example.com"}
    assert all(row.get("campaign_id") is None for row in pool)

    ba = await client.post(
        "/api/leads/bulk-assign",
        headers=headers,
        json={"lead_ids": lead_ids, "campaign_id": campaign_id},
    )
    assert ba.status_code == 200
    assert ba.json()["updated"] == 2

    lr = await client.get(
        f"/api/campaigns/{campaign_id}/leads",
        headers=headers,
    )
    assert lr.status_code == 200
    assigned = lr.json()
    assert len(assigned) == 2
    emails = {row["email"] for row in assigned}
    assert emails == {"alice@example.com", "bob@example.com"}


@pytest.mark.asyncio
async def test_import_csv_maps_website_column_to_website_url(client: AsyncClient) -> None:
    headers = await _auth_header()
    csv_body = (
        "email,company_name,link\ncarol@example.com,CarolCo,https://carol.example/page\n"
    )
    files = {"file": ("leads.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")}
    ir = await client.post("/api/leads/import", headers=headers, files=files)
    assert ir.status_code == 200
    assert ir.json()["created"] == 1

    all_lr = await client.get("/api/leads", headers=headers)
    assert all_lr.status_code == 200
    pool = all_lr.json()
    row = next(r for r in pool if r["email"] == "carol@example.com")
    assert row.get("website_url") == "https://carol.example/page"
    assert row.get("maps_url") in (None, "")
