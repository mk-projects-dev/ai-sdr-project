from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin
from app.database import get_db
from app.models import Admin, Campaign
from app.schemas_campaigns import CampaignCreate, CampaignRead, CampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


async def _get_campaign_or_404(
    campaign_id: UUID, db: AsyncSession
) -> Campaign:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.get("", response_model=list[CampaignRead])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> list[Campaign]:
    result = await db.execute(select(Campaign).order_by(Campaign.name.asc()))
    return list(result.scalars().all())


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> Campaign:
    campaign = Campaign(
        name=body.name,
        system_prompt=body.system_prompt,
        first_email_rules=body.first_email_rules,
        follow_up_rules=body.follow_up_rules,
        status=body.status,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> Campaign:
    return await _get_campaign_or_404(campaign_id, db)


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: UUID,
    body: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> Campaign:
    campaign = await _get_campaign_or_404(campaign_id, db)
    data = body.model_dump(exclude_unset=True)
    if not data:
        return campaign
    for key, value in data.items():
        setattr(campaign, key, value)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> None:
    await _get_campaign_or_404(campaign_id, db)
    await db.execute(delete(Campaign).where(Campaign.id == campaign_id))
    await db.commit()
