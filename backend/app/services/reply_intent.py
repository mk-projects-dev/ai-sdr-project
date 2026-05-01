from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from app.config import Settings
from app.models import Lead, LeadStatus
from app.services.json_text import parse_json_object_from_text

logger = logging.getLogger(__name__)

_CLASSIFIER_SYSTEM = """You classify replies to B2B cold outreach emails.
Respond with a single JSON object only, no markdown fences:
{"lead_status": "interested" | "replied" | "rejected", "note": "short reason"}

Semantics:
- interested: clear buying intent, wants demo/call/pricing, meeting acceptance
- rejected: unsubscribe, not interested, refusal, spam complaint
- replied: neutral reply, question, out-of-office, ambiguous / thread continuation without clear intent
"""


async def classify_inbound_reply(
    *,
    settings: Settings,
    lead: Lead,
    subject: str,
    body: str,
) -> tuple[LeadStatus, str]:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    user_block = (
        f"Incoming reply\n"
        f"Subject: {subject}\n\n"
        f"Body:\n{body or '(empty)'}\n\n"
        f"Lead email on file: {lead.email}\n"
        f"Lead company hint: {lead.company_name or '(unknown)'}\n"
    )

    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=_CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": user_block}],
    )

    text_parts: list[str] = []
    for block in message.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    combined = "".join(text_parts).strip()
    if not combined:
        raise RuntimeError("Empty classifier response")

    try:
        data = parse_json_object_from_text(combined)
        raw_status = str(data.get("lead_status", "")).strip().lower()
        note = str(data.get("note", "")).strip()[:512]
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Bad JSON from classifier: %s", combined[:400])
        raise RuntimeError("Classifier returned invalid JSON") from e

    mapping = {
        "interested": LeadStatus.interested,
        "replied": LeadStatus.replied,
        "rejected": LeadStatus.rejected,
    }
    status = mapping.get(raw_status, LeadStatus.replied)
    if not note:
        note = raw_status or "inbound_classified"

    return status, note
