from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.profile import CandidateProfile
from app.schemas.profile import CandidateProfileSchema, CandidateProfileSummarySchema

router = APIRouter()


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
