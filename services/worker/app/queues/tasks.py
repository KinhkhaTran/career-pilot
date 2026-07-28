"""
ARQ queue task definitions.

Phase 2 adds:
  - discover_jobs_task: fetch, normalize, and upsert jobs for one ATS source.

All tasks are idempotent via the discovery_run idempotency_key.
No submission, CAPTCHA, credential, or proxy-rotation code is permitted here.
"""

from __future__ import annotations

import logging

from .browser_runs import assisted_application_task

logger = logging.getLogger(__name__)


async def ping_task(ctx: dict[str, object]) -> str:
    """Health check task. Used to verify the worker is alive."""
    logger.info("Worker ping received")
    return "pong"


async def discover_jobs_task(
    ctx: dict[str, object],
    *,
    source: str,
    company_id: str,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """
    Discover, normalize, and upsert public job postings for one ATS source.

    Parameters
    ----------
    source:
        ATS source name: "greenhouse" | "lever" | "ashby"
    company_id:
        Board token, company slug, or organization ID for the ATS.
    idempotency_key:
        Optional caller-supplied key to prevent duplicate runs.
        Auto-generated if not provided.

    Returns
    -------
    dict with keys: run_id, discovered, upserted, skipped
    """
    from app.queues.discovery import discover_source

    return await discover_source(source, company_id, idempotency_key=idempotency_key)


async def startup(ctx: dict[str, object]) -> None:
    logger.info("Worker starting up (Phase 2)")


async def shutdown(ctx: dict[str, object]) -> None:
    logger.info("Worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = None  # set dynamically in main.py
    functions = [ping_task, discover_jobs_task, assisted_application_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 600
    keep_result = 3600
