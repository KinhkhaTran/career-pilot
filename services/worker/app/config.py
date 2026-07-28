from __future__ import annotations

from typing import Any, Literal

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

    # Scheduler: run discovery on a cron and auto-match afterwards.
    discovery_scheduler_enabled: bool = True
    # Minutes of the hour at which the scheduled discovery cron fires.
    discovery_schedule_minutes: str = "0"
    # Base URL of the API service, used to trigger match refresh after discovery.
    api_base_url: str = "http://localhost:8000"


worker_settings = WorkerSettings()


def get_redis_settings() -> Any:
    """Build ARQ RedisSettings from the configured REDIS_URL.

    Shared by the worker entrypoint and the operational CLI so both connect to
    the same Redis (honouring locally remapped ports) instead of ARQ defaults.
    """
    from urllib.parse import urlparse

    from arq.connections import RedisSettings

    u = urlparse(worker_settings.redis_url)
    return RedisSettings(
        host=u.hostname or "localhost",
        port=u.port or 6379,
        database=int((u.path or "/0").lstrip("/") or 0),
    )
