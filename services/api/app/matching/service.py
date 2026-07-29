"""
Shared match persistence.

Both `POST /matches/refresh` and the preference-driven `POST /jobs/search` need
the same fingerprinted, idempotent upsert, so it lives here rather than being
written twice. Computing a match never creates or mutates an application.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.engine import MatchConstraints, evaluate_match, fingerprint_inputs
from app.models.job import Job
from app.models.match import Match
from app.models.profile import CandidateProfile

_CONFLICT_COLUMNS = ["job_id", "candidate_profile_id", "profile_version", "input_fingerprint"]


def profile_payload(profile: CandidateProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "version": profile.version,
        "skills": profile.skills,
        "summary": profile.summary,
        "work_experience": profile.work_experience,
        "education": profile.education,
        "contact_info": profile.contact_info,
    }


def job_payload(job: Job) -> dict[str, Any]:
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


async def upsert_match(
    db: AsyncSession,
    *,
    job: Job,
    profile: CandidateProfile,
    constraints: MatchConstraints,
) -> tuple[Match, bool]:
    """
    Score one job against one profile version and persist the result.

    Returns ``(match, created)``. Identical inputs produce the same fingerprint
    and therefore reuse the stored row instead of writing a duplicate.
    """
    job_data = job_payload(job)
    profile_data = profile_payload(profile)
    fingerprint = fingerprint_inputs(job_data, profile_data, constraints)
    result = evaluate_match(job_data, profile_data, constraints)
    values = {
        "job_id": job.id,
        "candidate_profile_id": profile.id,
        "profile_version": profile.version,
        "input_fingerprint": fingerprint,
        "eligible": result.eligible,
        "score": result.score,
        "reasons": result.reasons,
        "explanation": result.explanation,
    }

    dialect = db.bind.dialect.name if db.bind is not None else ""
    insert_stmt: Any = None
    if dialect == "sqlite":
        insert_stmt = (
            sqlite_insert(Match).values(**values).on_conflict_do_nothing(
                index_elements=_CONFLICT_COLUMNS
            )
        )
    elif dialect == "postgresql":
        insert_stmt = (
            postgres_insert(Match).values(**values).on_conflict_do_nothing(
                constraint="uq_match_input"
            )
        )

    created = False
    if insert_stmt is not None:
        insert_result = await db.execute(insert_stmt)
        await db.flush()
        created = getattr(insert_result, "rowcount", 0) == 1

    stored = (
        await db.execute(
            select(Match).where(
                Match.job_id == job.id,
                Match.candidate_profile_id == profile.id,
                Match.profile_version == profile.version,
                Match.input_fingerprint == fingerprint,
            )
        )
    ).scalar_one()
    return stored, created
