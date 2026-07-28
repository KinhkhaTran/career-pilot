"""
Read-only discovery run endpoints.

Returns discovery run status and event history. Does not trigger new runs —
discovery is initiated by the ARQ worker scheduler.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.discovery_run import DiscoveryRun, DiscoveryRunEvent
from app.schemas.discovery_run import (
    DiscoveryRunEventSchema,
    DiscoveryRunSchema,
    DiscoveryRunSummarySchema,
)

router = APIRouter()


@router.get("", response_model=list[DiscoveryRunSummarySchema])
async def list_discovery_runs(
    source: str | None = Query(default=None, description="Filter by ATS source"),
    status: str | None = Query(default=None, description="Filter by run status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryRunSummarySchema]:
    """List discovery runs, newest first."""
    stmt = select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(limit).offset(offset)
    if source is not None:
        stmt = stmt.where(DiscoveryRun.source == source)
    if status is not None:
        stmt = stmt.where(DiscoveryRun.status == status)

    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [DiscoveryRunSummarySchema.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=DiscoveryRunSchema)
async def get_discovery_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> DiscoveryRunSchema:
    """Return a single discovery run with its event log."""
    stmt = (
        select(DiscoveryRun)
        .options(selectinload(DiscoveryRun.events))
        .where(DiscoveryRun.id == run_id)
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Discovery run {run_id!r} not found")
    return DiscoveryRunSchema.model_validate(run)


@router.get("/{run_id}/events", response_model=list[DiscoveryRunEventSchema])
async def list_discovery_run_events(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryRunEventSchema]:
    """Return the append-only event log for a discovery run."""
    run_check = await db.execute(
        select(DiscoveryRun.id).where(DiscoveryRun.id == run_id)
    )
    if run_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Discovery run {run_id!r} not found")

    stmt = (
        select(DiscoveryRunEvent)
        .where(DiscoveryRunEvent.discovery_run_id == run_id)
        .order_by(DiscoveryRunEvent.created_at)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [DiscoveryRunEventSchema.model_validate(e) for e in events]
