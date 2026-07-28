"""Small operational CLI for safe public discovery tasks."""

from __future__ import annotations

import argparse
import asyncio

from arq import create_pool
from arq.connections import RedisSettings


async def enqueue_discovery(source: str, company_id: str) -> None:
    redis = await create_pool(RedisSettings())
    try:
        await redis.enqueue_job(
            "discover_jobs_task",
            source=source,
            company_id=company_id,
        )
    finally:
        await redis.close()
    print(f"Enqueued discover_jobs_task for {source}:{company_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CareerPilot worker operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser("discover", help="enqueue public ATS discovery")
    discover.add_argument("source", choices=("greenhouse", "lever", "ashby"))
    discover.add_argument("company_id")
    args = parser.parse_args()
    if args.command == "discover":
        asyncio.run(enqueue_discovery(args.source, args.company_id))


if __name__ == "__main__":
    main()
