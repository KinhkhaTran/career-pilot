"""
Worker database access.

The worker writes discovery results directly to PostgreSQL using
SQLAlchemy Core (no ORM). This avoids importing the API service's
ORM models while still producing valid DB records that the API reads.

For tests, DATABASE_URL is overridden to an in-memory SQLite URL.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.config import worker_settings

# ---------------------------------------------------------------------------
# Table declarations (Core, not ORM) — must stay in sync with the migration
# ---------------------------------------------------------------------------
_metadata = sa.MetaData()

jobs_table = sa.Table(
    "jobs",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("external_id", sa.String(256), nullable=False),
    sa.Column("source", sa.String(64), nullable=False),
    sa.Column("source_url", sa.Text, nullable=False),
    sa.Column("title", sa.String(300), nullable=False),
    sa.Column("company", sa.String(200), nullable=False),
    sa.Column("location", sa.String(200)),
    sa.Column("is_remote", sa.Boolean, nullable=False, default=False),
    sa.Column("employment_type", sa.String(64)),
    sa.Column("salary_range", sa.JSON),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("requirements", sa.JSON),
    sa.Column("nice_to_have", sa.JSON),
    sa.Column("technologies", sa.JSON),
    sa.Column("status", sa.String(64), nullable=False, default="discovered"),
    sa.Column("snapshot_hash", sa.String(64), nullable=False),
    sa.Column("discovered_at", sa.DateTime(timezone=True)),
    sa.Column("posted_at", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
    sa.Column("normalized_at", sa.DateTime(timezone=True)),
)

discovery_runs_table = sa.Table(
    "discovery_runs",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("source", sa.String(64), nullable=False),
    sa.Column("company_id", sa.String(256), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, default="pending"),
    sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
    sa.Column("jobs_discovered", sa.Integer, nullable=False, default=0),
    sa.Column("jobs_upserted", sa.Integer, nullable=False, default=0),
    sa.Column("jobs_skipped", sa.Integer, nullable=False, default=0),
    sa.Column("error_message", sa.Text),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

discovery_run_events_table = sa.Table(
    "discovery_run_events",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("discovery_run_id", sa.String(36), nullable=False),
    sa.Column("event_type", sa.String(64), nullable=False),
    sa.Column("detail", sa.JSON),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(worker_settings.database_url, echo=False)
    return _engine


@asynccontextmanager
async def get_connection() -> AsyncIterator[AsyncConnection]:
    async with get_engine().begin() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Discovery run helpers
# ---------------------------------------------------------------------------


async def create_discovery_run(
    conn: AsyncConnection,
    *,
    source: str,
    company_id: str,
    idempotency_key: str,
) -> str:
    """Insert a new discovery run record and return its id."""
    run_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await conn.execute(
        discovery_runs_table.insert().values(
            id=run_id,
            source=source,
            company_id=company_id,
            status="pending",
            idempotency_key=idempotency_key,
            jobs_discovered=0,
            jobs_upserted=0,
            jobs_skipped=0,
            error_message=None,
            started_at=None,
            completed_at=None,
            created_at=now,
        )
    )
    return run_id


async def update_discovery_run_status(
    conn: AsyncConnection,
    run_id: str,
    *,
    status: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    jobs_discovered: int | None = None,
    jobs_upserted: int | None = None,
    jobs_skipped: int | None = None,
    error_message: str | None = None,
) -> None:
    values: dict[str, object] = {"status": status}
    if started_at is not None:
        values["started_at"] = started_at
    if completed_at is not None:
        values["completed_at"] = completed_at
    if jobs_discovered is not None:
        values["jobs_discovered"] = jobs_discovered
    if jobs_upserted is not None:
        values["jobs_upserted"] = jobs_upserted
    if jobs_skipped is not None:
        values["jobs_skipped"] = jobs_skipped
    if error_message is not None:
        values["error_message"] = error_message
    await conn.execute(
        discovery_runs_table.update().where(discovery_runs_table.c.id == run_id).values(**values)
    )


async def append_discovery_event(
    conn: AsyncConnection,
    run_id: str,
    event_type: str,
    detail: dict[str, object] | None = None,
) -> None:
    await conn.execute(
        discovery_run_events_table.insert().values(
            id=str(uuid.uuid4()),
            discovery_run_id=run_id,
            event_type=event_type,
            detail=detail or {},
            created_at=datetime.now(UTC),
        )
    )


# ---------------------------------------------------------------------------
# Job upsert helper
# ---------------------------------------------------------------------------


async def upsert_job(
    conn: AsyncConnection,
    *,
    external_id: str,
    source: str,
    source_url: str,
    title: str,
    company: str,
    location: str | None,
    is_remote: bool,
    employment_type: str | None,
    description: str,
    requirements: list[str],
    nice_to_have: list[str],
    technologies: list[str],
    snapshot_hash: str,
    posted_at: datetime | None,
    salary_range: dict[str, object] | None,
) -> str:
    """
    Insert-or-update a job row.

    Returns "upserted" if the row was created/updated, "skipped" if the
    snapshot hash is unchanged.
    """
    now = datetime.now(UTC)

    result = await conn.execute(
        sa.select(jobs_table.c.id, jobs_table.c.snapshot_hash).where(
            sa.and_(
                jobs_table.c.source == source,
                jobs_table.c.external_id == external_id,
            )
        )
    )
    row = result.fetchone()

    if row is None:
        job_id = str(uuid.uuid4())
        await conn.execute(
            jobs_table.insert().values(
                id=job_id,
                external_id=external_id,
                source=source,
                source_url=source_url,
                title=title,
                company=company,
                location=location,
                is_remote=is_remote,
                employment_type=employment_type,
                salary_range=salary_range,
                description=description,
                requirements=requirements,
                nice_to_have=nice_to_have,
                technologies=technologies,
                status="discovered",
                snapshot_hash=snapshot_hash,
                discovered_at=now,
                posted_at=posted_at,
                expires_at=None,
                normalized_at=now,
            )
        )
        return "upserted"

    if row.snapshot_hash == snapshot_hash:
        return "skipped"

    await conn.execute(
        jobs_table.update()
        .where(jobs_table.c.id == row.id)
        .values(
            source_url=source_url,
            title=title,
            company=company,
            location=location,
            is_remote=is_remote,
            employment_type=employment_type,
            salary_range=salary_range,
            description=description,
            requirements=requirements,
            nice_to_have=nice_to_have,
            technologies=technologies,
            snapshot_hash=snapshot_hash,
            posted_at=posted_at,
            normalized_at=now,
        )
    )
    return "upserted"
