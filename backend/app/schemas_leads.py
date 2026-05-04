from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models import LeadStatus


class LeadCreate(BaseModel):
    email: EmailStr
    first_name: Optional[str] = Field(default=None, max_length=255)
    company_name: Optional[str] = Field(default=None, max_length=512)
    pain_point: Optional[str] = None
    status: LeadStatus = LeadStatus.new


class LeadUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(default=None, max_length=255)
    company_name: Optional[str] = Field(default=None, max_length=512)
    pain_point: Optional[str] = None
    status: Optional[LeadStatus] = None


class LeadRead(BaseModel):
    id: UUID
    campaign_id: UUID
    email: str
    first_name: Optional[str]
    company_name: Optional[str]
    pain_point: Optional[str]
    source: Optional[str] = None
    status: LeadStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadImportRowError(BaseModel):
    row: int
    message: str


class LeadImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[LeadImportRowError]
