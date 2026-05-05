from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    replied = "replied"
    interested = "interested"
    rejected = "rejected"


class EmailDirection(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


class Admin(Base):
    __tablename__ = "admin"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    first_email_rules: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_rules: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, name="campaign_status", native_enum=True),
        nullable=False,
        default=CampaignStatus.draft,
    )
    max_emails_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50
    )
    send_delay_min_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
    send_delay_max_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1200
    )

    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="campaign")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pain_point: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="lead_status", native_enum=True),
        nullable=False,
        default=LeadStatus.new,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", back_populates="leads")
    email_interactions: Mapped[list["EmailInteraction"]] = relationship(
        "EmailInteraction", back_populates="lead"
    )


class ImapProcessedMessage(Base):
    """Дедупликация обработанных входящих писем по Message-ID (или синтетическому ключу)."""

    __tablename__ = "imap_processed_messages"

    message_id_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EmailInteraction(Base):
    __tablename__ = "email_interactions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[EmailDirection] = mapped_column(
        SAEnum(EmailDirection, name="email_direction", native_enum=True),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ai_intent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="email_interactions")
