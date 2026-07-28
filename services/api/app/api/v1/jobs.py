from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobSchema, JobSummarySchema

router = APIRouter()


@router.get("", response_model=list[JobSummarySchema])
async def list_jobs(
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[JobSummarySchema]:
    """List jobs with optional status filter, pagination."""
    stmt = select(Job).order_by(Job.discovered_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(Job.status == status)

    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return [JobSummarySchema.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobSchema)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> JobSchema:
    """Return a single job by id."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return JobSchema.model_validate(job)
