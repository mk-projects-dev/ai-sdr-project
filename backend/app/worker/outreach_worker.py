from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models import Campaign, CampaignStatus, EmailDirection, EmailInteraction, Lead, LeadStatus
from app.services.email_ai import generate_first_outreach_email
from app.services.mail_delivery import send_outreach_email

logger = logging.getLogger(__name__)

_pipeline_lock = asyncio.Lock()


def _start_of_day_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def _count_outbound_today_for_campaign(
    session: AsyncSession, campaign_id: UUID
) -> int:
    start = _start_of_day_utc()
    q = (
        select(func.count())
        .select_from(EmailInteraction)
        .join(Lead, EmailInteraction.lead_id == Lead.id)
        .where(
            Lead.campaign_id == campaign_id,
            EmailInteraction.direction == EmailDirection.outbound,
            EmailInteraction.ai_intent == "first_outreach",
            EmailInteraction.sent_at >= start,
        )
    )
    return int(await session.scalar(q) or 0)


async def _pick_next_lead(session: AsyncSession) -> Lead | None:
    """
    Берём oldest new-lead из активных кампаний, у которых не исчерпан дневной лимит исходящих.
    Лимит считается по UTC-календарному дню (совпадает с sent_at в БД).
    """
    stmt = (
        select(Lead)
        .join(Campaign, Lead.campaign_id == Campaign.id)
        .where(
            Lead.status == LeadStatus.new,
            Campaign.status == CampaignStatus.active,
        )
        .options(joinedload(Lead.campaign))
        .order_by(Lead.created_at.asc())
        .limit(50)
    )
    result = await session.execute(stmt)
    candidates = result.unique().scalars().all()
    for lead in candidates:
        if lead.campaign_id is None or lead.campaign is None:
            continue
        cap = lead.campaign.max_emails_per_day
        used = await _count_outbound_today_for_campaign(session, lead.campaign_id)
        if used < cap:
            return lead
    return None


async def process_outreach_once() -> bool:
    """
    Один проход: взять лида (new + активная кампания + не превышен дневной лимит),
    сгенерировать письмо, отправить SMTP, записать EmailInteraction и статус contacted.
    После успеха — случайная пауза между min/max секундам кампании (антиспам-поведение).
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return False

    async with _pipeline_lock:
        async with async_session_factory() as session:
            lead = await _pick_next_lead(session)
            if lead is None:
                return False

            campaign = lead.campaign
            lead_id: UUID = lead.id
            lead_email = lead.email
            lead_company_name = lead.company_name
            lead_pain_point = lead.pain_point
            system_prompt = campaign.system_prompt
            first_rules = campaign.first_email_rules
            delay_lo = min(
                campaign.send_delay_min_seconds,
                campaign.send_delay_max_seconds,
            )
            delay_hi = max(
                campaign.send_delay_min_seconds,
                campaign.send_delay_max_seconds,
            )

        subject: str | None = None
        body: str | None = None
        try:
            subject, body = await generate_first_outreach_email(
                settings=settings,
                system_prompt=system_prompt,
                first_email_rules=first_rules,
                lead_email=lead_email,
                lead_company_name=lead_company_name,
                lead_pain_point=lead_pain_point,
            )
            await send_outreach_email(
                settings=settings,
                to_email=lead_email,
                subject=subject,
                body=body,
            )
        except Exception:
            logger.exception("Outreach pipeline failed for lead_id=%s", lead_id)
            return False

        async with async_session_factory() as session:
            async with session.begin():
                fresh = await session.get(Lead, lead_id)
                if fresh is None:
                    logger.warning("Lead %s disappeared before commit", lead_id)
                    return False
                if fresh.status != LeadStatus.new:
                    logger.warning(
                        "Lead %s status is no longer new after send; skipping DB write",
                        lead_id,
                    )
                    return False
                fresh.status = LeadStatus.contacted
                session.add(
                    EmailInteraction(
                        lead_id=lead_id,
                        direction=EmailDirection.outbound,
                        subject=subject,
                        body=body,
                        ai_intent="first_outreach",
                    )
                )

        logger.info("Outreach stored for lead_id=%s", lead_id)

        wait_s = random.uniform(float(delay_lo), float(delay_hi))
        logger.info(
            "Outreach throttle: sleeping %.1fs (campaign random delay %s–%ss)",
            wait_s,
            delay_lo,
            delay_hi,
        )
        await asyncio.sleep(wait_s)
        return True


async def outreach_worker_loop() -> None:
    interval = get_settings().worker_poll_interval_seconds

    logger.info(
        "Outreach worker started (model=%s, dry_run=%s)",
        get_settings().anthropic_model,
        get_settings().outreach_dry_run,
    )

    try:
        while True:
            try:
                if not get_settings().anthropic_api_key:
                    await asyncio.sleep(min(interval, 30.0))
                    continue

                batch = max(1, get_settings().worker_batch_size)
                any_work = False
                for _ in range(batch):
                    if await process_outreach_once():
                        any_work = True
                    else:
                        break

                delay = 2.0 if any_work else interval
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outreach worker iteration error")
                await asyncio.sleep(interval)
    finally:
        logger.info("Outreach worker stopped")
