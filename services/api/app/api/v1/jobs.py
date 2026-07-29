from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.matching import upsert_match
from app.models.job import Job
from app.models.preference import CandidatePreference
from app.models.profile import CandidateProfile
from app.schemas.job import JobSchema, JobSummarySchema
from app.schemas.match import MatchSchema
from app.schemas.preference import PreferenceSchema
from app.schemas.search import JobSearchRequest, JobSearchResponse, SearchResultSchema

router = APIRouter()


def _job_text(job: Job) -> str:
    """Flatten the searchable text of a stored job for keyword filtering."""
    parts: list[Any] = [job.title, job.company, job.location, job.description]
    for collection in (job.requirements, job.nice_to_have, job.technologies):
        parts.extend(collection or [])
    return " ".join(str(part) for part in parts if part).lower()


def _meets_salary_floor(job: Job, min_salary: int | None) -> bool:
    """A job passes when its advertised maximum reaches the floor, or is unknown."""
    if min_salary is None:
        return True
    salary = job.salary_range or {}
    ceiling = salary.get("max") if isinstance(salary, dict) else None
    if not isinstance(ceiling, int | float):
        # Unpriced postings are kept rather than silently dropped.
        return True
    return float(ceiling) >= float(min_salary)


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


@router.post("/search", response_model=JobSearchResponse)
async def search_jobs(
    body: JobSearchRequest, db: AsyncSession = Depends(get_db)
) -> JobSearchResponse:
    """
    Rank stored jobs against a candidate's saved preferences.

    Search reads only jobs already in the database — it performs no outbound
    discovery — and persists a fingerprinted match per scored job so the score
    and its evidence are reproducible. It never creates or mutates applications.
    """
    profile_stmt = select(CandidateProfile).where(CandidateProfile.id == body.profile_id)
    if body.profile_version is not None:
        profile_stmt = profile_stmt.where(CandidateProfile.version == body.profile_version)
    profile = await db.scalar(profile_stmt.order_by(CandidateProfile.version.desc()).limit(1))
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {body.profile_id!r} version not found")

    stored_preference = await db.scalar(
        select(CandidatePreference)
        .where(CandidatePreference.candidate_profile_id == body.profile_id)
        .order_by(CandidatePreference.version.desc())
        .limit(1)
    )
    if stored_preference is None:
        raise HTTPException(
            status_code=409,
            detail="Save search preferences before running a preference-based search",
        )
    preferences = PreferenceSchema(
        candidate_profile_id=stored_preference.candidate_profile_id,
        version=stored_preference.version,
        remote_only=stored_preference.remote_only,
        allowed_locations=[str(i) for i in stored_preference.allowed_locations or []],
        employment_types=[str(i) for i in stored_preference.employment_types or []],
        keywords=[str(i) for i in stored_preference.keywords or []],
        min_salary=stored_preference.min_salary,
        created_at=stored_preference.created_at,  # type: ignore[arg-type]
    )
    constraints = preferences.constraints()

    jobs = list(
        (await db.execute(select(Job).order_by(Job.discovered_at.desc()))).scalars().all()
    )
    scanned = len(jobs)

    keywords = [keyword.lower() for keyword in preferences.keywords if keyword.strip()]
    candidates = [
        job
        for job in jobs
        if (not keywords or any(keyword in _job_text(job) for keyword in keywords))
        and _meets_salary_floor(job, preferences.min_salary)
    ]

    results: list[SearchResultSchema] = []
    for job in candidates:
        match, _ = await upsert_match(db, job=job, profile=profile, constraints=constraints)
        if body.eligible_only and not match.eligible:
            continue
        results.append(
            SearchResultSchema(
                job=JobSummarySchema.model_validate(job),
                source_url=job.source_url,
                match=MatchSchema.model_validate(match),
            )
        )

    results.sort(key=lambda item: (-item.match.score, item.job.title))
    trimmed = results[: body.limit]
    return JobSearchResponse(
        profile_id=profile.id,
        profile_version=profile.version,
        preferences=preferences,
        scanned=scanned,
        filtered_out=scanned - len(trimmed),
        results=trimmed,
    )


@router.get("/{job_id}", response_model=JobSchema)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> JobSchema:
    """Return a single job by id."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return JobSchema.model_validate(job)
