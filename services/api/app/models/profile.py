from __future__ import annotations

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CandidateProfile(Base):
    """
    Versioned candidate profile.

    Append-only versioning: each update creates a new row with the same `id`
    but an incremented `version`. The "current" profile for a candidate is the
    row with the highest version for a given `id`.

    A unique constraint on (id, version) enforces version integrity.
    """

    __tablename__ = "candidate_profiles"

    # Surrogate primary key for the specific version row
    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Candidate identity — shared across versions
    id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Version number — starts at 1, incremented by the service layer
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Stored as JSON: { email, phone, location, linkedin, github, website }
    contact_info: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # List of WorkExperience objects
    work_experience: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    # List of Education objects
    education: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    # List of Certification objects
    certifications: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    # List of skill strings
    skills: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    # List of { language, proficiency } objects
    languages: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        # Enforce uniqueness of (candidate_id, version)
        __import__("sqlalchemy").UniqueConstraint("id", "version", name="uq_profile_id_version"),
    )
