from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import aiosmtplib

from app.config import Settings

logger = logging.getLogger(__name__)


async def send_outreach_email(
    *,
    settings: Settings,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    """Отправляет письмо через SMTP: multipart/alternative (plain + HTML).

    Plain часть — запасной вариант для клиентов без HTML; HTML часть ренерит теги вроде ``<br>``, ``<b>``.
    """
    if settings.outreach_dry_run:
        logger.info(
            "[dry-run] Would send email to=%s subject=%r (not sending)",
            to_email,
            subject[:80],
        )
        return

    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL must be set for real sends")

    msg = EmailMessage()
    msg_domain = (
        settings.smtp_from_email.split("@")[-1]
        if settings.smtp_from_email and "@" in settings.smtp_from_email
        else "localhost"
    )
    msg["Message-ID"] = make_msgid(domain=msg_domain)
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(body)  # plain text fallback
    msg.add_alternative(body, subtype="html")  # HTML version

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )
