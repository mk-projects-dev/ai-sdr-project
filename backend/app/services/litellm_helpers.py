"""Общие вызовы LiteLLM (модель, usage, cost) для Anthropic через единый API."""
from __future__ import annotations

import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)


def anthropic_litellm_model_id(anthropic_model: str) -> str:
    """Превращает id из .env в формат LiteLLM, например claude-… → anthropic/claude-…."""
    m = (anthropic_model or "").strip()
    if not m:
        return "anthropic/claude-3-5-sonnet-20241022"
    if "/" in m:
        return m
    return f"anthropic/{m}"


def completion_text_first_choice(response: Any) -> str:
    if not getattr(response, "choices", None):
        return ""
    choice = response.choices[0]
    msg = getattr(choice, "message", None)
    if msg is None:
        return ""
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(getattr(block, "text", "")))
        return "".join(parts).strip()
    return str(content or "").strip()


def usage_tokens_from_response(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    in_t = int(getattr(usage, "prompt_tokens", None) or 0)
    out_t = int(getattr(usage, "completion_tokens", None) or 0)
    return in_t, out_t


def completion_cost_safe(response: Any) -> float:
    try:
        c = litellm.completion_cost(completion_response=response)
        if c is None:
            return 0.0
        return round(float(c), 8)
    except Exception as e:
        logger.warning("litellm.completion_cost failed: %s", e)
        return 0.0
