from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.config import Settings, get_settings
from app.database import async_session_factory
from app.models import EmailDirection, EmailInteraction, ImapProcessedMessage, Lead
from app.services.imap_messages import RawImapMessage, fetch_unseen_messages, mark_messages_seen
from app.services.reply_intent import classify_inbound_reply

logger = logging.getLogger(__name__)

_BODY_PREVIEW = 4000


def _format_thread_context(interactions: list[EmailInteraction]) -> str | None:
    if not interactions:
        return None
    parts: list[str] = []
    for ix in interactions:
        label = "OUTBOUND" if ix.direction == EmailDirection.outbound else "INBOUND"
        body_preview = (ix.body or "")[:_BODY_PREVIEW]
        parts.append(
            f"[{label}] {ix.sent_at.isoformat()}\n"
            f"Subject: {ix.subject}\n{body_preview}"
        )
    return "\n\n---\n\n".join(parts)


async def _process_one_inbound(m: RawImapMessage, settings: Settings) -> None:
    async with async_session_factory() as session:
        dup = await session.get(ImapProcessedMessage, m.message_id_key)
        if dup is not None:
            await asyncio.to_thread(mark_messages_seen, settings, [m.sequence_num])
            return

    follow_up_rules: str | None = None
    thread_context: str | None = None
    async with async_session_factory() as session:
        result = await session.execute(
            select(Lead)
            .where(func.lower(Lead.email) == m.from_email)
            .options(joinedload(Lead.campaign))
        )
        lead = result.unique().scalar_one_or_none()
        if lead is not None:
            if lead.campaign is not None:
                follow_up_rules = lead.campaign.follow_up_rules
            hist = await session.execute(
                select(EmailInteraction)
                .where(EmailInteraction.lead_id == lead.id)
                .order_by(EmailInteraction.sent_at.asc())
                .limit(25)
            )
            thread_context = _format_thread_context(list(hist.scalars().all()))

    if lead is None:
        logger.info(
            "IMAP: no lead for sender %s (message_id=%s), marking processed+seen",
            m.from_email,
            m.message_id_key[:80],
        )
        async with async_session_factory() as session:
            async with session.begin():
                session.add(ImapProcessedMessage(message_id_key=m.message_id_key, lead_id=None))
        await asyncio.to_thread(mark_messages_seen, settings, [m.sequence_num])
        return

    try:
        new_status, intent_note = await classify_inbound_reply(
            settings=settings,
            lead=lead,
            subject=m.subject,
            body=m.body_text,
            follow_up_rules=follow_up_rules,
            thread_context=thread_context,
        )
    except Exception:
        logger.exception(
            "IMAP: classification failed for message_id=%s lead=%s",
            m.message_id_key[:80],
            lead.id,
        )
        return

    async with async_session_factory() as session:
        async with session.begin():
            dup2 = await session.get(ImapProcessedMessage, m.message_id_key)
            if dup2 is not None:
                return
            fresh = await session.get(Lead, lead.id)
            if fresh is None:
                return
            fresh.status = new_status
            session.add(
                EmailInteraction(
                    lead_id=lead.id,
                    direction=EmailDirection.inbound,
                    subject=m.subject[:1024],
                    body=(m.body_text or "(empty)")[:],
                    ai_intent=intent_note[:512],
                )
            )
            session.add(
                ImapProcessedMessage(message_id_key=m.message_id_key, lead_id=lead.id)
            )

    await asyncio.to_thread(mark_messages_seen, settings, [m.sequence_num])
    logger.info(
        "IMAP: processed inbound from %s -> status=%s",
        m.from_email,
        new_status.value,
    )


async def imap_reply_worker_loop() -> None:
    logger.info("IMAP reply worker loop starting")

    try:
        while True:
            settings = get_settings()
            if (
                not settings.imap_host
                or not settings.imap_user
                or not settings.imap_password
            ):
                await asyncio.sleep(60.0)
                continue
            if not settings.anthropic_api_key:
                await asyncio.sleep(60.0)
                continue

            try:
                messages = await asyncio.to_thread(fetch_unseen_messages, settings)
                for msg in messages:
                    await _process_one_inbound(msg, settings)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("IMAP fetch/process cycle failed")

            await asyncio.sleep(settings.imap_poll_interval_seconds)
    finally:
        logger.info("IMAP reply worker stopped")
