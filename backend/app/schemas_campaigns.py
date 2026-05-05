from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models import CampaignStatus


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    system_prompt: str = Field(min_length=1)
    first_email_rules: str = Field(min_length=1)
    follow_up_rules: str = Field(min_length=1)
    status: CampaignStatus = CampaignStatus.draft
    max_emails_per_day: int = Field(default=50, ge=1, le=2000)
    send_delay_min_seconds: int = Field(default=300, ge=60, le=86_400)
    send_delay_max_seconds: int = Field(default=1200, ge=60, le=86_400)

    @model_validator(mode="after")
    def delay_order(self) -> CampaignCreate:
        if self.send_delay_max_seconds < self.send_delay_min_seconds:
            raise ValueError("send_delay_max_seconds must be >= send_delay_min_seconds")
        return self


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    system_prompt: Optional[str] = Field(default=None, min_length=1)
    first_email_rules: Optional[str] = Field(default=None, min_length=1)
    follow_up_rules: Optional[str] = Field(default=None, min_length=1)
    status: Optional[CampaignStatus] = None
    max_emails_per_day: Optional[int] = Field(default=None, ge=1, le=2000)
    send_delay_min_seconds: Optional[int] = Field(default=None, ge=60, le=86_400)
    send_delay_max_seconds: Optional[int] = Field(default=None, ge=60, le=86_400)

    @model_validator(mode="after")
    def delay_order(self) -> CampaignUpdate:
        mn = self.send_delay_min_seconds
        mx = self.send_delay_max_seconds
        if mn is not None and mx is not None and mx < mn:
            raise ValueError("send_delay_max_seconds must be >= send_delay_min_seconds")
        return self


class CampaignRead(BaseModel):
    id: UUID
    name: str
    system_prompt: str
    first_email_rules: str
    follow_up_rules: str
    status: CampaignStatus
    max_emails_per_day: int
    send_delay_min_seconds: int
    send_delay_max_seconds: int

    model_config = {"from_attributes": True}
