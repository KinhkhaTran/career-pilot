from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://careerpilot:careerpilot@localhost:5432/careerpilot"
    # For tests, override to: "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"
    # CRITICAL safety setting — must always be "stop_before_submit" in initial release
    initial_submission_mode: Literal["stop_before_submit", "allow_submit"] = "stop_before_submit"


settings = Settings()
