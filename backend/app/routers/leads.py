from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth import get_current_admin
from app.csv_leads import parse_csv_leads
from app.database import get_db
from app.models import Admin, Campaign, EmailInteraction, Lead, LeadStatus
from app.schemas_leads import (
    EmailInteractionRead,
    LeadBulkAssign,
    LeadBulkAssignResult,
    LeadCreate,
    LeadImportResult,
    LeadImportRowError,
    LeadRead,
    LeadUpdate,
)

router = APIRouter(tags=["leads"])


def _lead_to_read(lead: Lead) -> LeadRead:
    return LeadRead(
        id=lead.id,
        campaign_id=lead.campaign_id,
        campaign_name=lead.campaign.name if lead.campaign is not None else None,
        email=str(lead.email),
        company_name=lead.company_name,
        pain_point=lead.pain_point,
        source=lead.source,
        status=lead.status,
        created_at=lead.created_at,
    )


async def _get_campaign_or_404(campaign_id: UUID, db: AsyncSession) -> Campaign:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


async def _get_lead_or_404(lead_id: UUID, db: AsyncSession) -> Lead:
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id).options(joinedload(Lead.campaign))
    )
    lead = result.unique().scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.get("/leads", response_model=list[LeadRead])
async def list_all_leads(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> list[LeadRead]:
    result = await db.execute(
        select(Lead)
        .options(joinedload(Lead.campaign))
        .order_by(Lead.created_at.desc())
    )
    rows = result.unique().scalars().all()
    return [_lead_to_read(x) for x in rows]


@router.post("/leads/import", response_model=LeadImportResult)
async def import_leads_csv_global(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> LeadImportResult:
    content = await file.read()
    rows, parse_errors = parse_csv_leads(content)
    errors: list[LeadImportRowError] = [
        LeadImportRowError(row=r, message=m) for r, m in parse_errors
    ]
    created = 0
    skipped = 0

    for row in rows:
        lead = Lead(
            campaign_id=None,
            email=row["email"],
            company_name=row.get("company_name"),
            pain_point=row.get("pain_point"),
            status=LeadStatus.new,
        )
        db.add(lead)
        try:
            await db.commit()
            created += 1
        except IntegrityError:
            await db.rollback()
            skipped += 1

    return LeadImportResult(created=created, skipped=skipped, errors=errors)


@router.post("/leads/bulk-assign", response_model=LeadBulkAssignResult)
async def bulk_assign_leads(
    body: LeadBulkAssign,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> LeadBulkAssignResult:
    await _get_campaign_or_404(body.campaign_id, db)
    unique_ids = list(dict.fromkeys(body.lead_ids))
    result = await db.execute(
        select(Lead).where(Lead.id.in_(unique_ids)).options(joinedload(Lead.campaign))
    )
    leads = result.unique().scalars().all()
    found = {lg.id for lg in leads}
    missing = set(unique_ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leads not found: {sorted(str(i) for i in missing)}",
        )
    for lg in leads:
        lg.campaign_id = body.campaign_id
    await db.commit()
    return LeadBulkAssignResult(updated=len(leads))


@router.get("/campaigns/{campaign_id}/leads", response_model=list[LeadRead])
async def list_leads(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> list[LeadRead]:
    await _get_campaign_or_404(campaign_id, db)
    result = await db.execute(
        select(Lead)
        .where(Lead.campaign_id == campaign_id)
        .options(joinedload(Lead.campaign))
        .order_by(Lead.created_at.desc())
    )
    rows = result.unique().scalars().all()
    return [_lead_to_read(x) for x in rows]


@router.post(
    "/campaigns/{campaign_id}/leads",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead(
    campaign_id: UUID,
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> LeadRead:
    await _get_campaign_or_404(campaign_id, db)
    lead = Lead(
        campaign_id=campaign_id,
        email=body.email,
        company_name=body.company_name,
        pain_point=body.pain_point,
        status=body.status,
    )
    db.add(lead)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists for another lead",
        ) from None
    await db.refresh(lead)
    lead_loaded = await _get_lead_or_404(lead.id, db)
    return _lead_to_read(lead_loaded)


@router.get("/leads/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> LeadRead:
    lead = await _get_lead_or_404(lead_id, db)
    return _lead_to_read(lead)


@router.get("/leads/{lead_id}/interactions", response_model=list[EmailInteractionRead])
async def list_lead_interactions(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> list[EmailInteractionRead]:
    await _get_lead_or_404(lead_id, db)
    result = await db.execute(
        select(EmailInteraction)
        .where(EmailInteraction.lead_id == lead_id)
        .order_by(EmailInteraction.sent_at.asc())
    )
    rows = result.scalars().all()
    return [EmailInteractionRead.model_validate(x) for x in rows]


@router.patch("/leads/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: UUID,
    body: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> LeadRead:
    lead = await _get_lead_or_404(lead_id, db)
    data = body.model_dump(exclude_unset=True)
    if not data:
        return _lead_to_read(lead)
    for key, value in data.items():
        setattr(lead, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from None
    updated = await _get_lead_or_404(lead_id, db)
    return _lead_to_read(updated)


@router.delete("/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> None:
    await _get_lead_or_404(lead_id, db)
    await db.execute(delete(Lead).where(Lead.id == lead_id))
    await db.commit()
