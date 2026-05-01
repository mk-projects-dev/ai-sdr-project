from __future__ import annotations

from sqlalchemy import select

from app.auth import hash_password
from app.config import get_settings
from app.database import async_session_factory
from app.models import Admin


async def ensure_initial_admin() -> None:
    settings = get_settings()
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(Admin).where(Admin.email == settings.initial_admin_email)
        )
        if result.scalar_one_or_none() is not None:
            return

        session.add(
            Admin(
                email=settings.initial_admin_email,
                hashed_password=hash_password(settings.initial_admin_password),
            )
        )
        await session.commit()
