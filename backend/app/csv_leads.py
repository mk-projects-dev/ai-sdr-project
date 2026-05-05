from __future__ import annotations

import csv
import io
import re
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError


def _normalize_header(key: str) -> str:
    return re.sub(r"\s+", "_", key.strip().lower())


# Заголовок CSV → каноническое поле лида
_HEADER_MAP: dict[str, str] = {
    "email": "email",
    "e-mail": "email",
    "mail": "email",
    "company_name": "company_name",
    "company": "company_name",
    "organization": "company_name",
    "org": "company_name",
    "name": "company_name",
    "pain_point": "pain_point",
    "pain": "pain_point",
    "painpoint": "pain_point",
}


def _map_row(raw: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in raw.items():
        nk = _normalize_header(key)
        canon = _HEADER_MAP.get(nk)
        if canon is None:
            continue
        if canon in out and out[canon]:
            continue
        v = (val or "").strip()
        out[canon] = v if v else None
    return out


def parse_csv_leads(content: bytes) -> tuple[list[dict[str, Any]], list[tuple[int, str]]]:
    """
    Возвращает список строк-диктов (email обязателен на этапе валидации выше)
    и список ошибок (номер строки в файле, сообщение).
    """
    text = content.decode("utf-8-sig")
    if not text.strip():
        return [], [(1, "Пустой файл")]

    errors: list[tuple[int, str]] = []
    dialect = csv.excel
    try:
        sample = text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        pass

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return [], [(1, "Нет заголовков CSV")]

    rows_out: list[dict[str, Any]] = []
    for i, raw in enumerate(reader, start=2):
        if not any((v or "").strip() for v in raw.values()):
            continue
        mapped = _map_row({k: v for k, v in raw.items() if k})
        email_raw = mapped.get("email")
        if not email_raw:
            errors.append((i, "Нет колонки email или значение пустое"))
            continue
        try:
            email_norm = str(TypeAdapter(EmailStr).validate_python(email_raw))
        except ValidationError:
            errors.append((i, "Некорректный email"))
            continue

        rows_out.append(
            {
                "email": email_norm,
                "company_name": mapped.get("company_name"),
                "pain_point": mapped.get("pain_point"),
            }
        )

    return rows_out, errors
