"""
ARQ queue task definitions.

All tasks are safe, read-only operations in Phase 1.
Phase 2 will add job discovery tasks backed by ATS adapters.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def ping_task(ctx: dict[str, object]) -> str:
    """Health check task. Used to verify the worker is alive."""
    logger.info("Worker ping received")
    return "pong"


async def startup(ctx: dict[str, object]) -> None:
    logger.info("Worker starting up")


async def shutdown(ctx: dict[str, object]) -> None:
    logger.info("Worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""

    from app.config import worker_settings as _ws

    redis_settings = None  # set dynamically in main.py
    functions = [ping_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
