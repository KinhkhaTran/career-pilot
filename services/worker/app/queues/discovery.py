"""
Job discovery orchestration.

Drives the discover → normalize → upsert pipeline for a single
(source, company_id) pair. Called by the ARQ discovery task.

All operations are idempotent:
  - The discovery_run row carries an idempotency_key.
  - Jobs are upserted with snapshot_hash deduplication.
  - Discovery run events are append-only.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.adapters.base import ATSAdapter, NormalizedJobData, RetryExhaustedError
from app.adapters.normalizer import normalize
from app.db import (
    append_discovery_event,
    get_connection,
    update_discovery_run_status,
    upsert_job,
)

logger = logging.getLogger(__name__)


async def run_discovery(
    adapter: ATSAdapter,
    run_id: str,
) -> dict[str, int]:
    """
    Execute a single discovery run for the given adapter.

    Updates discovery_run status and appends audit events.
    Returns counts: {discovered, upserted, skipped}.
    """
    discovered = 0
    upserted = 0
    skipped = 0

    async with get_connection() as conn:
        await update_discovery_run_status(
            conn, run_id, status="running", started_at=datetime.now(UTC)
        )
        await append_discovery_event(
            conn,
            run_id,
            "run_started",
            {
                "source": adapter.source_name,
            },
        )

    try:
        normalized_batch: list[NormalizedJobData] = []

        async for raw in adapter.discover_jobs():
            normalized = normalize(raw)
            normalized_batch.append(normalized)
            discovered += 1

        logger.info(
            "Discovery %r: %d jobs fetched from source=%r",
            run_id,
            discovered,
            adapter.source_name,
        )

        for norm in normalized_batch:
            async with get_connection() as conn:
                result = await upsert_job(
                    conn,
                    external_id=norm.external_id,
                    source=norm.source,
                    source_url=norm.source_url,
                    title=norm.title,
                    company=norm.company,
                    location=norm.location,
                    is_remote=norm.is_remote,
                    employment_type=norm.employment_type,
                    description=norm.description,
                    requirements=norm.requirements,
                    nice_to_have=norm.nice_to_have,
                    technologies=norm.technologies,
                    snapshot_hash=norm.snapshot_hash,
                    posted_at=norm.posted_at,
                    salary_range=norm.salary_range,
                )
            if result == "upserted":
                upserted += 1
            else:
                skipped += 1

        async with get_connection() as conn:
            await append_discovery_event(
                conn,
                run_id,
                "batch_discovered",
                {
                    "discovered": discovered,
                    "upserted": upserted,
                    "skipped": skipped,
                },
            )
            await update_discovery_run_status(
                conn,
                run_id,
                status="completed",
                completed_at=datetime.now(UTC),
                jobs_discovered=discovered,
                jobs_upserted=upserted,
                jobs_skipped=skipped,
            )
            await append_discovery_event(
                conn,
                run_id,
                "run_completed",
                {
                    "discovered": discovered,
                    "upserted": upserted,
                    "skipped": skipped,
                },
            )

        logger.info(
            "Discovery %r completed: discovered=%d upserted=%d skipped=%d",
            run_id,
            discovered,
            upserted,
            skipped,
        )

    except RetryExhaustedError as exc:
        error_msg = str(exc)
        logger.error("Discovery %r failed (retry exhausted): %s", run_id, error_msg)
        async with get_connection() as conn:
            await update_discovery_run_status(
                conn,
                run_id,
                status="failed",
                completed_at=datetime.now(UTC),
                jobs_discovered=discovered,
                jobs_upserted=upserted,
                jobs_skipped=skipped,
                error_message=error_msg,
            )
            await append_discovery_event(
                conn,
                run_id,
                "run_failed",
                {
                    "error": error_msg,
                    "discovered_before_failure": discovered,
                },
            )
        raise

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error("Discovery %r failed unexpectedly: %s", run_id, error_msg, exc_info=True)
        async with get_connection() as conn:
            await update_discovery_run_status(
                conn,
                run_id,
                status="failed",
                completed_at=datetime.now(UTC),
                jobs_discovered=discovered,
                jobs_upserted=upserted,
                jobs_skipped=skipped,
                error_message=error_msg,
            )
            await append_discovery_event(
                conn,
                run_id,
                "run_failed",
                {
                    "error": error_msg,
                    "discovered_before_failure": discovered,
                },
            )
        raise

    return {"discovered": discovered, "upserted": upserted, "skipped": skipped}
