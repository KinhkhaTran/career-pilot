"""
Scheduled discovery + auto-match orchestration.

A single ARQ cron entrypoint (``scheduled_discovery``) that:
  1. Reads the enabled discovery sources from the database.
  2. Runs read-only public discovery for each source (resilient per source).
  3. Triggers a match refresh on the API so newly discovered jobs are scored
     against every candidate profile.

Safety boundary: discovery is read-only public ATS access only. The match
refresh call never creates or submits applications — it only recomputes local
match scores.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from app.config import worker_settings
from app.db import get_connection, get_enabled_sources
from app.queues.discovery import discover_source

logger = logging.getLogger(__name__)

_MATCH_REFRESH_TIMEOUT_S = 60.0


def _as_int(value: object) -> int:
    """Coerce a discovery-result count to int, defaulting to 0."""
    return value if isinstance(value, int) else 0


async def trigger_match_refresh() -> dict[str, object] | None:
    """Ask the API to recompute matches for all profiles. Best-effort.

    Returns the API summary, or None if the API is unreachable. A discovery
    cycle must not fail just because matching could not be triggered.
    """
    url = f"{worker_settings.api_base_url.rstrip('/')}/api/v1/matches/refresh-all"
    try:
        async with httpx.AsyncClient(timeout=_MATCH_REFRESH_TIMEOUT_S) as client:
            resp = await client.post(url)
            resp.raise_for_status()
            result: dict[str, object] = resp.json()
            logger.info("Match refresh triggered: %s", result)
            return result
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.warning("Match refresh could not be triggered (%s): %s", type(exc).__name__, exc)
        return None


async def scheduled_discovery(ctx: dict[str, object]) -> dict[str, object]:
    """ARQ cron entrypoint: discover all enabled sources, then auto-match."""
    cycle = datetime.now(UTC).strftime("%Y%m%dT%H%M")

    async with get_connection() as conn:
        sources = await get_enabled_sources(conn)

    if not sources:
        logger.info("Scheduled discovery: no enabled sources configured; nothing to do")
        return {"cycle": cycle, "sources": 0, "discovered": 0, "matched": False}

    logger.info("Scheduled discovery cycle %s: %d enabled source(s)", cycle, len(sources))

    total_discovered = 0
    total_upserted = 0
    failures = 0
    for entry in sources:
        source = entry["source"]
        company_id = entry["company_id"]
        # Cycle-scoped idempotency key: distinct per cron tick so each cycle
        # re-fetches, but still de-duplicates concurrent runs of the same tick.
        ikey = f"sched:{cycle}:{source}:{company_id}"
        try:
            result = await discover_source(source, company_id, idempotency_key=ikey)
            total_discovered += _as_int(result.get("discovered", 0))
            total_upserted += _as_int(result.get("upserted", 0))
        except Exception as exc:  # noqa: BLE001 — one bad source must not kill the cycle
            failures += 1
            logger.error(
                "Scheduled discovery failed for %s:%s — %s: %s",
                source,
                company_id,
                type(exc).__name__,
                exc,
            )

    refresh = await trigger_match_refresh()

    summary = {
        "cycle": cycle,
        "sources": len(sources),
        "failures": failures,
        "discovered": total_discovered,
        "upserted": total_upserted,
        "matched": refresh is not None,
    }
    logger.info("Scheduled discovery cycle %s complete: %s", cycle, summary)
    return summary
