from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models import EmailDirection, LeadStatus


class LeadBulkAssign(BaseModel):
    lead_ids: list[UUID] = Field(..., min_length=1)
    campaign_id: UUID


class LeadBulkAssignResult(BaseModel):
    updated: int


class LeadCreate(BaseModel):
    email: EmailStr
    company_name: Optional[str] = Field(default=None, max_length=512)
    pain_point: Optional[str] = None
    status: LeadStatus = LeadStatus.new


class LeadUpdate(BaseModel):
    email: Optional[EmailStr] = None
    company_name: Optional[str] = Field(default=None, max_length=512)
    pain_point: Optional[str] = None
    status: Optional[LeadStatus] = None


class LeadRead(BaseModel):
    id: UUID
    campaign_id: Optional[UUID] = None
    campaign_name: Optional[str] = None
    email: str
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


class EmailInteractionRead(BaseModel):
    id: UUID
    direction: EmailDirection
    subject: str
    body: str
    ai_intent: Optional[str] = None
    sent_at: datetime

    model_config = {"from_attributes": True}
