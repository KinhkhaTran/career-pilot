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
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
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
    sa.UniqueConstraint("source", "external_id", name="uq_job_source_external_id"),
    sa.Index("ix_jobs_snapshot_hash", "snapshot_hash"),
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

browser_runs_table = sa.Table(
    "browser_runs",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("status", sa.String(64), nullable=False),
    sa.Column("stopped_before_submit", sa.Boolean, nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
)

browser_run_steps_table = sa.Table(
    "browser_run_steps",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("run_id", sa.String(36), nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("detail", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

browser_run_events_table = sa.Table(
    "browser_run_events",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("run_id", sa.String(36), nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.Column("event_type", sa.String(100), nullable=False),
    sa.Column("detail", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

browser_screenshots_table = sa.Table(
    "browser_screenshots",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("run_id", sa.String(36), nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.Column("label", sa.String(100), nullable=False),
    sa.Column("path", sa.Text, nullable=False),
    sa.Column("sha256", sa.String(64)),
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
) -> tuple[str, bool]:
    """Atomically create a run, returning ``(run_id, created)``."""
    run_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    values = {
        "id": run_id,
        "source": source,
        "company_id": company_id,
        "status": "pending",
        "idempotency_key": idempotency_key,
        "jobs_discovered": 0,
        "jobs_upserted": 0,
        "jobs_skipped": 0,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
    }
    try:
        async with conn.begin_nested():
            await conn.execute(discovery_runs_table.insert().values(**values))
    except IntegrityError:
        pass

    result = await conn.execute(
        sa.select(discovery_runs_table.c.id).where(
            discovery_runs_table.c.idempotency_key == idempotency_key
        )
    )
    existing = result.scalar_one()
    return str(existing), str(existing) == run_id


async def get_discovery_run_result(conn: AsyncConnection, run_id: str) -> dict[str, object]:
    """Return the current persisted result for an idempotent replay."""
    result = await conn.execute(
        sa.select(
            discovery_runs_table.c.status,
            discovery_runs_table.c.jobs_discovered,
            discovery_runs_table.c.jobs_upserted,
            discovery_runs_table.c.jobs_skipped,
        ).where(discovery_runs_table.c.id == run_id)
    )
    row = result.one()
    return {
        "status": str(row.status),
        "discovered": int(row.jobs_discovered),
        "upserted": int(row.jobs_upserted),
        "skipped": int(row.jobs_skipped),
    }


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


async def persist_browser_run_result(
    conn: AsyncConnection,
    run_id: str,
    *,
    status: str,
    stopped_before_submit: bool,
    steps: list[dict[str, object]],
    events: list[dict[str, object]],
    screenshots: list[dict[str, str]],
) -> None:
    """Persist an assisted-run result returned by the supervised browser worker."""
    now = datetime.now(UTC)
    await conn.execute(
        browser_runs_table.update()
        .where(browser_runs_table.c.id == run_id)
        .values(
            status=status,
            stopped_before_submit=stopped_before_submit,
            completed_at=now,
        )
    )
    for sequence, step in enumerate(steps):
        action = str(step.get("action", "unknown"))
        detail = {key: value for key, value in step.items() if key != "action"}
        await conn.execute(
            browser_run_steps_table.insert().values(
                id=str(uuid.uuid4()),
                run_id=run_id,
                sequence=sequence,
                action=action,
                detail=detail,
                created_at=now,
            )
        )
    for sequence, event in enumerate(events):
        event_type = str(event.get("type", "unknown"))
        detail = {key: value for key, value in event.items() if key != "type"}
        await conn.execute(
            browser_run_events_table.insert().values(
                id=str(uuid.uuid4()),
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                detail=detail,
                created_at=now,
            )
        )
    for sequence, screenshot in enumerate(screenshots):
        await conn.execute(
            browser_screenshots_table.insert().values(
                id=str(uuid.uuid4()),
                run_id=run_id,
                sequence=sequence,
                label=screenshot["label"],
                path=screenshot["path"],
                sha256=None,
                created_at=now,
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
    """Atomically insert or update a job by its source/external-id key."""
    now = datetime.now(UTC)
    values = {
        "id": str(uuid.uuid4()),
        "external_id": external_id,
        "source": source,
        "source_url": source_url,
        "title": title,
        "company": company,
        "location": location,
        "is_remote": is_remote,
        "employment_type": employment_type,
        "salary_range": salary_range,
        "description": description,
        "requirements": requirements,
        "nice_to_have": nice_to_have,
        "technologies": technologies,
        "status": "discovered",
        "snapshot_hash": snapshot_hash,
        "discovered_at": now,
        "posted_at": posted_at,
        "expires_at": None,
        "normalized_at": now,
    }
    insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    statement = insert(jobs_table).values(**values)
    update_values = {
        key: statement.excluded[key]
        for key in (
            "source_url",
            "title",
            "company",
            "location",
            "is_remote",
            "employment_type",
            "salary_range",
            "description",
            "requirements",
            "nice_to_have",
            "technologies",
            "snapshot_hash",
            "posted_at",
            "normalized_at",
        )
    }
    statement = statement.on_conflict_do_update(
        index_elements=["source", "external_id"],
        set_=update_values,
        where=jobs_table.c.snapshot_hash != statement.excluded.snapshot_hash,
    )
    result = await conn.execute(statement)
    return "upserted" if result.rowcount else "skipped"
