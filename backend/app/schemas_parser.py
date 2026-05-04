from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ParserRunRequest(BaseModel):
    """Тело POST /api/parser/run. Лиды привязываются к кампании (FK в БД)."""

    campaign_id: UUID
    location: str = Field(..., min_length=1, max_length=256, examples=["Киев"])
    keyword: str = Field(..., min_length=1, max_length=256, examples=["стоматология"])
    limit: int = Field(10, ge=1, le=50)


class ParserRunResponse(BaseModel):
    status: str = "started"
