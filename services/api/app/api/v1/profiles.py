from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.preference import CandidatePreference
from app.models.profile import CandidateProfile
from app.schemas.preference import PreferenceSchema, PreferenceWriteSchema
from app.schemas.profile import (
    CandidateProfileCreateSchema,
    CandidateProfileSchema,
    CandidateProfileSummarySchema,
)

router = APIRouter()


def _profile_columns(body: CandidateProfileCreateSchema) -> dict[str, object]:
    """Map the write payload onto the versioned profile columns."""
    return {
        "full_name": body.full_name,
        "contact_info": body.contact_info.model_dump() if body.contact_info else None,
        "summary": body.summary,
        "work_experience": [item.model_dump() for item in body.work_experience],
        "education": [item.model_dump() for item in body.education],
        "certifications": [item.model_dump() for item in body.certifications],
        "skills": list(body.skills),
        "languages": list(body.languages),
    }


def _contact_text(profile: CandidateProfile, key: str) -> str | None:
    """Read a string field from the JSON contact payload safely."""
    value = (profile.contact_info or {}).get(key)
    return value if isinstance(value, str) else None


@router.get("", response_model=list[CandidateProfileSummarySchema])
async def list_profiles(db: AsyncSession = Depends(get_db)) -> list[CandidateProfileSummarySchema]:
    """
    List the current version of every candidate profile.

    "Current" is defined as the row with the maximum version for each candidate id.
    """
    # Subquery: max version per candidate id
    from sqlalchemy import func as sqlfunc

    subq = (
        select(
            CandidateProfile.id,
            sqlfunc.max(CandidateProfile.version).label("max_version"),
        )
        .group_by(CandidateProfile.id)
        .subquery()
    )

    stmt = select(CandidateProfile).join(
        subq,
        (CandidateProfile.id == subq.c.id)
        & (CandidateProfile.version == subq.c.max_version),
    )

    result = await db.execute(stmt)
    profiles = result.scalars().all()

    return [
        CandidateProfileSummarySchema(
            id=p.id,
            version=p.version,
            full_name=p.full_name,
            email=_contact_text(p, "email"),
            location=_contact_text(p, "location"),
            created_at=p.created_at,  # type: ignore[arg-type]
            updated_at=p.updated_at,  # type: ignore[arg-type]
        )
        for p in profiles
    ]


@router.get("/{profile_id}", response_model=CandidateProfileSchema)
async def get_profile(
    profile_id: str, db: AsyncSession = Depends(get_db)
) -> CandidateProfileSchema:
    """Return the latest version of a candidate profile by candidate id."""

    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.id == profile_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id!r} not found")

    return CandidateProfileSchema.model_validate(profile)


@router.get("/{profile_id}/versions", response_model=list[CandidateProfileSummarySchema])
async def list_profile_versions(
    profile_id: str, db: AsyncSession = Depends(get_db)
) -> list[CandidateProfileSummarySchema]:
    """Return all versions of a candidate profile ordered newest first."""
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.id == profile_id)
        .order_by(CandidateProfile.version.desc())
    )
    result = await db.execute(stmt)
    profiles = result.scalars().all()
    if not profiles:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id!r} not found")

    return [
        CandidateProfileSummarySchema(
            id=p.id,
            version=p.version,
            full_name=p.full_name,
            email=_contact_text(p, "email"),
            location=_contact_text(p, "location"),
            created_at=p.created_at,  # type: ignore[arg-type]
            updated_at=p.updated_at,  # type: ignore[arg-type]
        )
        for p in profiles
    ]


def _preference_schema(preference: CandidatePreference) -> PreferenceSchema:
    return PreferenceSchema(
        candidate_profile_id=preference.candidate_profile_id,
        version=preference.version,
        remote_only=preference.remote_only,
        allowed_locations=[str(item) for item in preference.allowed_locations or []],
        employment_types=[str(item) for item in preference.employment_types or []],
        keywords=[str(item) for item in preference.keywords or []],
        min_salary=preference.min_salary,
        created_at=preference.created_at,  # type: ignore[arg-type]
    )


@router.post("", response_model=CandidateProfileSchema, status_code=201)
async def create_profile(
    body: CandidateProfileCreateSchema, db: AsyncSession = Depends(get_db)
) -> CandidateProfileSchema:
    """Create a brand-new candidate at version 1."""
    profile = CandidateProfile(id=str(uuid.uuid4()), version=1, **_profile_columns(body))
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return CandidateProfileSchema.model_validate(profile)


@router.put("/{profile_id}", response_model=CandidateProfileSchema)
async def update_profile(
    profile_id: str, body: CandidateProfileCreateSchema, db: AsyncSession = Depends(get_db)
) -> CandidateProfileSchema:
    """
    Append a new version of an existing candidate profile.

    Profiles are append-only: earlier versions stay readable, so a packet
    fingerprint that pinned an older version keeps resolving.
    """
    latest = await db.scalar(
        select(func.max(CandidateProfile.version)).where(CandidateProfile.id == profile_id)
    )
    if latest is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id!r} not found")

    for _ in range(3):
        profile = CandidateProfile(id=profile_id, version=latest + 1, **_profile_columns(body))
        try:
            async with db.begin_nested():
                db.add(profile)
                await db.flush()
            await db.refresh(profile)
            return CandidateProfileSchema.model_validate(profile)
        except IntegrityError:
            refreshed = await db.scalar(
                select(func.max(CandidateProfile.version)).where(
                    CandidateProfile.id == profile_id
                )
            )
            if refreshed is None:
                raise HTTPException(
                    status_code=404, detail=f"Profile {profile_id!r} not found"
                ) from None
            latest = refreshed
    raise HTTPException(status_code=409, detail="Concurrent profile version conflict; retry")


@router.get("/{profile_id}/preferences", response_model=PreferenceSchema)
async def get_preferences(profile_id: str, db: AsyncSession = Depends(get_db)) -> PreferenceSchema:
    """Return the latest saved search preferences for a candidate."""
    preference = await db.scalar(
        select(CandidatePreference)
        .where(CandidatePreference.candidate_profile_id == profile_id)
        .order_by(CandidatePreference.version.desc())
        .limit(1)
    )
    if preference is None:
        raise HTTPException(
            status_code=404, detail=f"No saved preferences for profile {profile_id!r}"
        )
    return _preference_schema(preference)


@router.put("/{profile_id}/preferences", response_model=PreferenceSchema)
async def save_preferences(
    profile_id: str, body: PreferenceWriteSchema, db: AsyncSession = Depends(get_db)
) -> PreferenceSchema:
    """Save a new version of the candidate's search preferences."""
    profile_exists = await db.scalar(
        select(CandidateProfile.row_id).where(CandidateProfile.id == profile_id)
    )
    if profile_exists is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id!r} not found")

    for _ in range(3):
        latest = await db.scalar(
            select(func.max(CandidatePreference.version)).where(
                CandidatePreference.candidate_profile_id == profile_id
            )
        )
        preference = CandidatePreference(
            candidate_profile_id=profile_id,
            version=(latest or 0) + 1,
            remote_only=body.remote_only,
            allowed_locations=list(body.allowed_locations),
            employment_types=list(body.employment_types),
            keywords=list(body.keywords),
            min_salary=body.min_salary,
        )
        try:
            async with db.begin_nested():
                db.add(preference)
                await db.flush()
            await db.refresh(preference)
            return _preference_schema(preference)
        except IntegrityError:
            continue
    raise HTTPException(status_code=409, detail="Concurrent preference version conflict; retry")
