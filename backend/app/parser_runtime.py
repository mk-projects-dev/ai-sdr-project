"""Состояние фонового парсера Maps (один воркер, последовательные BackgroundTasks)."""

from __future__ import annotations

from datetime import datetime, timezone

_busy = False
_last_finished_at: str | None = None
_last_created_count: int = 0


def mark_started() -> str:
    """Помечает старт текущего запуска; возвращает ISO-время старта для ответа клиенту."""
    global _busy
    _busy = True
    return datetime.now(timezone.utc).isoformat()


def mark_finished(created_count: int) -> None:
    global _busy, _last_finished_at, _last_created_count
    _busy = False
    _last_finished_at = datetime.now(timezone.utc).isoformat()
    _last_created_count = max(0, int(created_count))


def snapshot() -> tuple[bool, str | None, int]:
    return _busy, _last_finished_at, _last_created_count
