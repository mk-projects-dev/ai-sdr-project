from __future__ import annotations

import email
import email.policy
import hashlib
import imaplib
from dataclasses import dataclass
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from app.config import Settings


def _decode_header_value(raw: Optional[str]) -> str:
    if not raw:
        return ""
    parts: list[str] = []
    for chunk, charset in decode_header(raw):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


def _extract_plain_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                return str(payload or "")
        return ""
    if msg.get_content_type() == "text/plain":
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        return str(payload or "")
    return ""


def _normalize_message_id(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1]
    return s.strip()


@dataclass(frozen=True)
class RawImapMessage:
    """Одно непрочитанное письмо из ящика."""

    sequence_num: bytes
    message_id_key: str
    from_email: str
    subject: str
    body_text: str
    received_hint: str


def _connect(settings: Settings) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
    if settings.imap_use_ssl:
        return imaplib.IMAP4_SSL(settings.imap_host or "", settings.imap_port)
    return imaplib.IMAP4(settings.imap_host or "", settings.imap_port)


def fetch_unseen_messages(settings: Settings) -> list[RawImapMessage]:
    """
    Синхронно: подключение к IMAP, выбор ящика, поиск UNSEEN, разбор писем.
    Вызывать из потока через asyncio.to_thread.
    """
    if not settings.imap_host or not settings.imap_user or not settings.imap_password:
        return []

    out: list[RawImapMessage] = []
    mail = _connect(settings)
    try:
        mail.login(settings.imap_user, settings.imap_password)
        mail.select(settings.imap_mailbox or "INBOX")

        typ, data = mail.search(None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return []

        for num in data[0].split():
            typ, msg_data = mail.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw_bytes = msg_data[0][1]
            if not isinstance(raw_bytes, bytes):
                continue
            msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

            mid_raw = msg.get("Message-ID")
            mid = _normalize_message_id(mid_raw)
            if not mid:
                subj = _decode_header_value(msg.get("Subject"))
                date_hdr = msg.get("Date") or ""
                h = hashlib.sha256(f"{subj}\n{date_hdr}".encode("utf-8")).hexdigest()[:40]
                mid = f"synthetic:{h}"

            from_raw = msg.get("From")
            _, addr = parseaddr(from_raw or "")
            from_email = (addr or "").strip().lower()
            if not from_email:
                continue

            subject = _decode_header_value(msg.get("Subject"))
            body = _extract_plain_body(msg).strip()
            if len(body) > 120_000:
                body = body[:120_000] + "\n…"

            date_hdr = msg.get("Date")
            received_hint = ""
            if date_hdr:
                try:
                    received_hint = str(parsedate_to_datetime(date_hdr))
                except (TypeError, ValueError, OverflowError):
                    received_hint = date_hdr

            out.append(
                RawImapMessage(
                    sequence_num=num,
                    message_id_key=mid[:512],
                    from_email=from_email,
                    subject=subject[:1024],
                    body_text=body,
                    received_hint=received_hint,
                )
            )
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return out


def mark_messages_seen(settings: Settings, sequence_nums: list[bytes]) -> None:
    """Помечает письма как прочитанные по sequence number из FETCH."""
    if not sequence_nums or not settings.imap_host:
        return
    mail = _connect(settings)
    try:
        mail.login(settings.imap_user or "", settings.imap_password or "")
        mail.select(settings.imap_mailbox or "INBOX")
        for num in sequence_nums:
            mail.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            mail.logout()
        except Exception:
            pass
