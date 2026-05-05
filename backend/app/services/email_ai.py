from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import litellm

from app.config import Settings
from app.services.json_text import parse_json_object_from_text
from app.services.litellm_helpers import (
    anthropic_litellm_model_id,
    completion_cost_safe,
    completion_text_first_choice,
    usage_tokens_from_response,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FirstOutreachEmailResult:
    subject: str
    body: str
    input_tokens: int
    output_tokens: int
    cost: float


async def generate_first_outreach_email(
    *,
    settings: Settings,
    system_prompt: str,
    first_email_rules: str,
    lead_email: str,
    lead_company_name: Optional[str],
    lead_pain_point: Optional[str],
) -> FirstOutreachEmailResult:
    """Генерирует тему и текст первого исходящего письма (LiteLLM → Anthropic)."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    lead_block = (
        f"Lead:\n"
        f"- Email: {lead_email}\n"
        f"- Company / venue name: {lead_company_name or '(unknown)'}\n"
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

    model = anthropic_litellm_model_id(settings.anthropic_model)
    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4096,
        api_key=settings.anthropic_api_key,
    )

    combined = completion_text_first_choice(response)
    if not combined:
        raise RuntimeError("Empty response from model")

    try:
        data = parse_json_object_from_text(combined)
        subject = str(data["subject"]).strip()
        body = str(data["body"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse JSON from model, raw=%s", combined[:500])
        raise RuntimeError("Model response is not valid JSON with subject/body") from e

    if not subject or not body:
        raise RuntimeError("Subject or body empty after generation")

    in_tok, out_tok = usage_tokens_from_response(response)
    cost = completion_cost_safe(response)

    return FirstOutreachEmailResult(
        subject=subject,
        body=body,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost=cost,
    )
