from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    initial_admin_email: Optional[str] = None
    initial_admin_password: Optional[str] = None

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-4.6-sonnet"

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_use_tls: bool = True

    worker_poll_interval_seconds: float = 25.0
    worker_batch_size: int = 3
    outreach_dry_run: bool = False

    imap_host: Optional[str] = None
    imap_port: int = 993
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True
    imap_poll_interval_seconds: float = 90.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
