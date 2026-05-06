from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ParserRunRequest(BaseModel):
    """Тело POST /api/parser/run. Лиды попадают в общую базу без кампании (campaign_id=null)."""

    location: str = Field(..., min_length=1, max_length=256, examples=["Киев"])
    keyword: str = Field(..., min_length=1, max_length=256, examples=["стоматология"])
    limit: int = Field(10, ge=1, le=50)


class ParserRunResponse(BaseModel):
    status: str = "started"
    started_at: str


class ParserStatusResponse(BaseModel):
    busy: bool
    last_finished_at: Optional[str] = None
    last_created_count: int = 0
