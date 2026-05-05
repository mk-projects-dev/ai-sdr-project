from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin
from app.database import get_db
from app.models import Admin, EmailInteraction
from app.schemas import BillingSummaryResponse

router = APIRouter(tags=["billing"])


@router.get("/billing/summary", response_model=BillingSummaryResponse)
async def billing_summary(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
) -> BillingSummaryResponse:
    stmt = select(
        func.coalesce(func.sum(EmailInteraction.cost), 0.0),
        func.coalesce(func.sum(EmailInteraction.input_tokens), 0),
        func.coalesce(func.sum(EmailInteraction.output_tokens), 0),
    )
    row = (await db.execute(stmt)).one()
    total_cost = float(row[0] or 0.0)
    total_in = int(row[1] or 0)
    total_out = int(row[2] or 0)
    return BillingSummaryResponse(
        total_cost=round(total_cost, 8),
        total_input_tokens=total_in,
        total_output_tokens=total_out,
    )
