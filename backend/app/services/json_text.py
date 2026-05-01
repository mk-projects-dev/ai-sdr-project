from __future__ import annotations

import json
import re


def parse_json_object_from_text(text: str) -> dict:
    """Снимает опциональные markdown-заборы и парсит один JSON-объект."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return json.loads(raw)
