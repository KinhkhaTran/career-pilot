from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://careerpilot:careerpilot@localhost:5432/careerpilot"
    # For tests, override to: "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"
    # CRITICAL safety setting — must always be "stop_before_submit" in initial release.
    # Set to "allow_submit" ONLY to enable the explicitly authorized, token-gated
    # submission path (see docs/adr/0008). Even then, a submit requires a verified
    # one-time approval token bound to the exact application state.
    initial_submission_mode: Literal["stop_before_submit", "allow_submit"] = "stop_before_submit"
    # HMAC secret used to sign one-time approval tokens. Empty disables issuance.
    approval_signing_secret: str = ""


settings = Settings()
