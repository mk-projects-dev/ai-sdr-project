from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import CampaignStatus


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    system_prompt: str = Field(min_length=1)
    first_email_rules: str = Field(min_length=1)
    follow_up_rules: str = Field(min_length=1)
    status: CampaignStatus = CampaignStatus.draft


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    system_prompt: Optional[str] = Field(default=None, min_length=1)
    first_email_rules: Optional[str] = Field(default=None, min_length=1)
    follow_up_rules: Optional[str] = Field(default=None, min_length=1)
    status: Optional[CampaignStatus] = None


class CampaignRead(BaseModel):
    id: UUID
    name: str
    system_prompt: str
    first_email_rules: str
    follow_up_rules: str
    status: CampaignStatus

    model_config = {"from_attributes": True}
