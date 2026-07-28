"""
ARQ queue task definitions.

Phase 2 adds:
  - discover_jobs_task: fetch, normalize, and upsert jobs for one ATS source.

All tasks are idempotent via the discovery_run idempotency_key.
No submission, CAPTCHA, credential, or proxy-rotation code is permitted here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

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
    from app.adapters.ashby import AshbyAdapter
    from app.adapters.base import ATSAdapter
    from app.adapters.greenhouse import GreenhouseAdapter
    from app.adapters.lever import LeverAdapter
    from app.db import create_discovery_run, get_connection, get_discovery_run_result
    from app.queues.discovery import run_discovery

    ikey = idempotency_key or f"{source}:{company_id}"

    adapter_map: dict[str, Callable[[], ATSAdapter]] = {
        "greenhouse": lambda: GreenhouseAdapter(board_token=company_id),
        "lever": lambda: LeverAdapter(company_slug=company_id),
        "ashby": lambda: AshbyAdapter(organization_id=company_id),
    }

    factory = adapter_map.get(source)
    if factory is None:
        raise ValueError(f"Unknown ATS source: {source!r}. Valid: {list(adapter_map)}")

    adapter = factory()

    async with get_connection() as conn:
        run_id, created = await create_discovery_run(
            conn, source=source, company_id=company_id, idempotency_key=ikey
        )
        if not created:
            return {
                "run_id": run_id,
                "source": source,
                "company_id": company_id,
                **await get_discovery_run_result(conn, run_id),
            }

    logger.info(
        "Discovery task started: source=%r company_id=%r run_id=%r",
        source,
        company_id,
        run_id,
    )

    counts = await run_discovery(adapter, run_id)

    return {
        "run_id": run_id,
        "source": source,
        "company_id": company_id,
        **counts,
    }


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
