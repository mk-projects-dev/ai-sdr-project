from __future__ import annotations

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from app.config import Settings
from app.services.json_text import parse_json_object_from_text

logger = logging.getLogger(__name__)


async def generate_first_outreach_email(
    *,
    settings: Settings,
    system_prompt: str,
    first_email_rules: str,
    lead_email: str,
    lead_first_name: Optional[str],
    lead_company_name: Optional[str],
    lead_pain_point: Optional[str],
) -> tuple[str, str]:
    """Генерирует тему и текст первого исходящего письма через Claude."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    lead_block = (
        f"Lead:\n"
        f"- Email: {lead_email}\n"
        f"- First name: {lead_first_name or '(unknown)'}\n"
        f"- Company: {lead_company_name or '(unknown)'}\n"
        f"- Pain point / context: {lead_pain_point or '(not specified)'}\n"
    )

    user_prompt = (
        f"{lead_block}\n"
        f"---\n"
        f"Rules for the FIRST cold outreach email (follow strictly):\n{first_email_rules}\n"
        f"---\n"
        f"Respond with a single JSON object only, no markdown fences, with keys:\n"
        f'"subject": string (email subject line),\n'
        f'"body": string (plain text email body, no HTML).\n'
    )

    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text_parts: list[str] = []
    for block in message.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    combined = "".join(text_parts).strip()
    if not combined:
        raise RuntimeError("Empty response from Anthropic")

    try:
        data = parse_json_object_from_text(combined)
        subject = str(data["subject"]).strip()
        body = str(data["body"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse JSON from model, raw=%s", combined[:500])
        raise RuntimeError("Model response is not valid JSON with subject/body") from e

    if not subject or not body:
        raise RuntimeError("Subject or body empty after generation")

    return subject, body
