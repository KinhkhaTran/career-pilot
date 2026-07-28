"""ARQ worker entry point."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import worker_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def get_redis_settings() -> Any:
    from urllib.parse import urlparse

    from arq.connections import RedisSettings

    u = urlparse(worker_settings.redis_url)
    return RedisSettings(
        host=u.hostname or "localhost",
        port=u.port or 6379,
        database=int((u.path or "/0").lstrip("/")),
    )


async def main() -> None:
    from arq import Worker

    from app.queues.tasks import ping_task, shutdown, startup

    redis_settings = get_redis_settings()

    worker = Worker(
        functions=[ping_task],
        redis_settings=redis_settings,
        on_startup=startup,
        on_shutdown=shutdown,
        max_jobs=10,
        job_timeout=300,
    )
    await worker.async_run()


if __name__ == "__main__":
    asyncio.run(main())
