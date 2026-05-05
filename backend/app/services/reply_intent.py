from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import litellm

from app.config import Settings
from app.models import Lead, LeadStatus
from app.services.json_text import parse_json_object_from_text
from app.services.litellm_helpers import (
    anthropic_litellm_model_id,
    completion_cost_safe,
    completion_text_first_choice,
    usage_tokens_from_response,
)

logger = logging.getLogger(__name__)

_CLASSIFIER_SYSTEM_BASE = """You classify replies to B2B cold outreach emails.
Respond with a single JSON object only, no markdown fences:
{"lead_status": "interested" | "replied" | "rejected", "note": "short reason"}

Semantics:
- interested: clear buying intent, wants demo/call/pricing, meeting acceptance
- rejected: unsubscribe, not interested, refusal, spam complaint
- replied: neutral reply, question, out-of-office, ambiguous / thread continuation without clear intent

Use the conversation thread (if provided) for context. If campaign-specific follow-up rules are given,
apply them when deciding lead_status and what to write in "note" (next-step hint for humans).
"""


@dataclass(frozen=True)
class InboundClassifyResult:
    lead_status: LeadStatus
    note: str
    input_tokens: int
    output_tokens: int
    cost: float


async def classify_inbound_reply(
    *,
    settings: Settings,
    lead: Lead,
    subject: str,
    body: str,
    follow_up_rules: Optional[str] = None,
    thread_context: Optional[str] = None,
) -> InboundClassifyResult:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    system = _CLASSIFIER_SYSTEM_BASE
    if follow_up_rules and follow_up_rules.strip():
        system += (
            "\n\n---\nCampaign follow-up / reply-handling rules "
            "(interpret replies and suggested next steps accordingly):\n"
            + follow_up_rules.strip()
        )

    user_chunks: list[str] = []
    if thread_context and thread_context.strip():
        user_chunks.append(
            "Prior messages in this thread (chronological):\n"
            + thread_context.strip()
            + "\n\n---\n"
        )
    user_chunks.append(
        "Latest incoming reply\n"
        f"Subject: {subject}\n\n"
        f"Body:\n{body or '(empty)'}\n\n"
        f"Lead email on file: {lead.email}\n"
        f"Lead company hint: {lead.company_name or '(unknown)'}\n"
    )
    user_block = "".join(user_chunks)

    model = anthropic_litellm_model_id(settings.anthropic_model)
    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_block},
        ],
        max_tokens=1024,
        api_key=settings.anthropic_api_key,
    )

    combined = completion_text_first_choice(response)
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

    in_tok, out_tok = usage_tokens_from_response(response)
    cost = completion_cost_safe(response)

    return InboundClassifyResult(
        lead_status=status,
        note=note,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost=cost,
    )
