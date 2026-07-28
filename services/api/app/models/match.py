from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Match(Base):
    """Immutable input-specific matching result for a job/profile version."""

    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_version: Mapped[int] = mapped_column(nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "job_id", "candidate_profile_id", "profile_version", "input_fingerprint",
            name="uq_match_input",
        ),
    )
