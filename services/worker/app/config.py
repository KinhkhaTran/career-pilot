from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://careerpilot:careerpilot@localhost:5432/careerpilot"
    initial_submission_mode: Literal["stop_before_submit", "allow_submit"] = "stop_before_submit"
    max_retries: int = 3
    job_discovery_interval_seconds: int = 3600


worker_settings = WorkerSettings()
