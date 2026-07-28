"""ARQ worker entry point."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_redis_settings, worker_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _discovery_cron_jobs() -> list[Any]:
    """Build the scheduled-discovery cron job list, if the scheduler is enabled."""
    if not worker_settings.discovery_scheduler_enabled:
        logger.info("Discovery scheduler disabled; running worker without cron jobs")
        return []

    from arq import cron

    from app.queues.scheduler import scheduled_discovery

    minutes = {
        int(part)
        for part in worker_settings.discovery_schedule_minutes.split(",")
        if part.strip().isdigit()
    } or {0}
    logger.info(
        "Discovery scheduler enabled: firing at minute(s) %s and at worker startup",
        sorted(minutes),
    )
    return [cron(scheduled_discovery, minute=minutes, run_at_startup=True)]


async def main() -> None:
    from arq import Worker

    from app.queues.tasks import discover_jobs_task, ping_task, shutdown, startup

    redis_settings = get_redis_settings()

    worker = Worker(
        functions=[ping_task, discover_jobs_task],
        cron_jobs=_discovery_cron_jobs(),
        redis_settings=redis_settings,
        on_startup=startup,
        on_shutdown=shutdown,
        max_jobs=10,
        job_timeout=600,
        keep_result=3600,
    )
    await worker.async_run()


if __name__ == "__main__":
    asyncio.run(main())
