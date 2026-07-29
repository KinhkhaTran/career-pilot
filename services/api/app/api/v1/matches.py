from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.matching import upsert_match
from app.models.job import Job
from app.models.match import Match
from app.models.profile import CandidateProfile
from app.schemas.match import MatchRefreshResponse, MatchRefreshSchema, MatchSchema

router = APIRouter()


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

    results: list[MatchSchema] = []
    created = 0
    existing = 0
    for job in jobs:
        stored, was_created = await upsert_match(
            db, job=job, profile=profile, constraints=payload.constraints
        )
        if was_created:
            created += 1
        else:
            existing += 1
        results.append(MatchSchema.model_validate(stored))
    return MatchRefreshResponse(created=created, existing=existing, matches=results)
