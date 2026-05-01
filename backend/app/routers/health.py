from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_admin
from app.models import Admin
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(admin: Admin = Depends(get_current_admin)) -> HealthResponse:
    return HealthResponse(status="healthy", admin_id=admin.id)
