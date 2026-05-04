from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin
from app.database import get_db
from app.models import Admin, Campaign
from app.schemas_parser import ParserRunRequest, ParserRunResponse
from app.services.scraper_service import run_maps_parser_job

router = APIRouter(tags=["parser"])


@router.post("/parser/run", response_model=ParserRunResponse)
async def start_parser(
    body: ParserRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> ParserRunResponse:
    r = await db.execute(select(Campaign).where(Campaign.id == body.campaign_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    background_tasks.add_task(
        run_maps_parser_job,
        body.campaign_id,
        body.location.strip(),
        body.keyword.strip(),
        body.limit,
    )
    return ParserRunResponse()
