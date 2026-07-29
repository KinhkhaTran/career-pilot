from __future__ import annotations

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CandidatePreference(Base):
    """
    Versioned search preferences for one candidate.

    Append-only versioning mirrors `CandidateProfile`: saving preferences writes a
    new row with an incremented version, so a match fingerprint always names the
    exact preference version that produced it.
    """

    __tablename__ = "candidate_preferences"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Hard eligibility constraints — mirror `app.matching.engine.MatchConstraints`
    remote_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_locations: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    employment_types: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    # Soft search filters applied to stored jobs before scoring
    keywords: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    min_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("candidate_profile_id", "version", name="uq_preference_version"),
    )
