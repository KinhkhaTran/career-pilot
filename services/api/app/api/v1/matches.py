from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.matching.engine import MatchConstraints, evaluate_match, fingerprint_inputs
from app.models.job import Job
from app.models.match import Match
from app.models.profile import CandidateProfile
from app.schemas.match import (
    MatchRefreshAllResponse,
    MatchRefreshResponse,
    MatchRefreshSchema,
    MatchSchema,
    ProfileRefreshSummary,
)

router = APIRouter()


def _profile_payload(profile: CandidateProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "version": profile.version,
        "skills": profile.skills,
        "summary": profile.summary,
        "work_experience": profile.work_experience,
        "education": profile.education,
        "contact_info": profile.contact_info,
    }


def _job_payload(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "snapshot_hash": job.snapshot_hash,
        "title": job.title,
        "location": job.location,
        "is_remote": job.is_remote,
        "employment_type": job.employment_type,
        "requirements": job.requirements,
        "nice_to_have": job.nice_to_have,
        "technologies": job.technologies,
        "description": job.description,
    }


@router.get("", response_model=list[MatchSchema])
async def list_matches(
    profile_id: str | None = Query(default=None),
    profile_version: int | None = Query(default=None, ge=1),
    eligible: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MatchSchema]:
    stmt = select(Match).order_by(Match.score.desc(), Match.created_at.desc()).limit(limit).offset(offset)
    if profile_id is not None:
        stmt = stmt.where(Match.candidate_profile_id == profile_id)
    if profile_version is not None:
        stmt = stmt.where(Match.profile_version == profile_version)
    if eligible is not None:
        stmt = stmt.where(Match.eligible == eligible)
    result = await db.execute(stmt)
    return [MatchSchema.model_validate(item) for item in result.scalars().all()]


@router.get("/{match_id}", response_model=MatchSchema)
async def get_match(match_id: str, db: AsyncSession = Depends(get_db)) -> MatchSchema:
    item = await db.get(Match, match_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id!r} not found")
    return MatchSchema.model_validate(item)


@router.post("/refresh", response_model=MatchRefreshResponse)
async def refresh_matches(
    payload: MatchRefreshSchema, db: AsyncSession = Depends(get_db)
) -> MatchRefreshResponse:
    """Compute local matches only; this endpoint never creates or changes applications."""
    profile_stmt = select(CandidateProfile).where(CandidateProfile.id == payload.profile_id)
    if payload.profile_version is not None:
        profile_stmt = profile_stmt.where(CandidateProfile.version == payload.profile_version)
    profile_stmt = profile_stmt.order_by(CandidateProfile.version.desc()).limit(1)
    profile = (await db.execute(profile_stmt)).scalar_one_or_none()
    if profile is None:
        detail = f"Profile {payload.profile_id!r} version not found"
        raise HTTPException(status_code=404, detail=detail)

    jobs_stmt = select(Job).order_by(Job.discovered_at.desc())
    if payload.job_ids is not None:
        jobs_stmt = jobs_stmt.where(Job.id.in_(payload.job_ids))
    jobs = list((await db.execute(jobs_stmt)).scalars().all())
    if payload.job_ids is not None and len(jobs) != len(set(payload.job_ids)):
        raise HTTPException(status_code=404, detail="One or more requested jobs were not found")

    created, existing, results = await _score_jobs_for_profile(
        db, profile, jobs, payload.constraints
    )
    return MatchRefreshResponse(created=created, existing=existing, matches=results)


async def _score_jobs_for_profile(
    db: AsyncSession,
    profile: CandidateProfile,
    jobs: list[Job],
    constraints: MatchConstraints,
) -> tuple[int, int, list[MatchSchema]]:
    """Score every job for one profile, upserting Match rows idempotently.

    Returns (created, existing, matches). Never creates or mutates applications.
    """
    profile_data = _profile_payload(profile)
    results: list[MatchSchema] = []
    created = 0
    existing = 0
    for job in jobs:
        job_data = _job_payload(job)
        fingerprint = fingerprint_inputs(job_data, profile_data, constraints)
        result = evaluate_match(job_data, profile_data, constraints)
        values = {
            "job_id": job.id, "candidate_profile_id": profile.id, "profile_version": profile.version,
            "input_fingerprint": fingerprint, "eligible": result.eligible, "score": result.score,
            "reasons": result.reasons, "explanation": result.explanation,
        }
        dialect = db.bind.dialect.name if db.bind is not None else ""
        insert_stmt: Any = None
        if dialect == "sqlite":
            insert_stmt = sqlite_insert(Match).values(**values).on_conflict_do_nothing(
                index_elements=["job_id", "candidate_profile_id", "profile_version", "input_fingerprint"]
            )
        elif dialect == "postgresql":
            insert_stmt = postgres_insert(Match).values(**values).on_conflict_do_nothing(
                constraint="uq_match_input"
            )
        else:
            insert_stmt = None
        if insert_stmt is not None:
            insert_result = await db.execute(insert_stmt)
            await db.flush()
            was_created = getattr(insert_result, "rowcount", 0) == 1
        else:
            was_created = False
        existing_item = (await db.execute(select(Match).where(
            Match.job_id == job.id,
            Match.candidate_profile_id == profile.id,
            Match.profile_version == profile.version,
            Match.input_fingerprint == fingerprint,
        ))).scalar_one()
        if was_created:
            created += 1
        else:
            existing += 1
        results.append(MatchSchema.model_validate(existing_item))
    return created, existing, results


@router.post("/refresh-all", response_model=MatchRefreshAllResponse)
async def refresh_all_matches(db: AsyncSession = Depends(get_db)) -> MatchRefreshAllResponse:
    """Recompute matches for every candidate profile at its latest version.

    Called by the discovery scheduler after a discovery cycle so newly
    discovered jobs are scored automatically. Never creates or submits
    applications — it only refreshes local match scores.
    """
    latest_version = (
        select(
            CandidateProfile.id.label("pid"),
            func.max(CandidateProfile.version).label("maxv"),
        )
        .group_by(CandidateProfile.id)
        .subquery()
    )
    profiles = list(
        (
            await db.execute(
                select(CandidateProfile).join(
                    latest_version,
                    (CandidateProfile.id == latest_version.c.pid)
                    & (CandidateProfile.version == latest_version.c.maxv),
                )
            )
        )
        .scalars()
        .all()
    )
    jobs = list((await db.execute(select(Job))).scalars().all())

    constraints = MatchConstraints()
    total_created = 0
    total_existing = 0
    per_profile: list[ProfileRefreshSummary] = []
    for profile in profiles:
        created, existing, _ = await _score_jobs_for_profile(db, profile, jobs, constraints)
        total_created += created
        total_existing += existing
        per_profile.append(
            ProfileRefreshSummary(
                profile_id=profile.id,
                profile_version=profile.version,
                created=created,
                existing=existing,
            )
        )
    return MatchRefreshAllResponse(
        profiles=len(profiles),
        jobs=len(jobs),
        created=total_created,
        existing=total_existing,
        per_profile=per_profile,
    )
