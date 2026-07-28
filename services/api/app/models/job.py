from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Job(Base):
    """Normalised job posting snapshot."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Source identity
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "greenhouse", "lever"
    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Job details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Structured data from normalisation
    salary_range: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    nice_to_have: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    technologies: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="discovered"
    )  # discovered | matched | archived

    # Content-addressable dedup key (SHA-256 hex of canonical snapshot fields)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Timestamps
    discovered_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    posted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Prevent duplicate ingestion of the same external posting
        __import__("sqlalchemy").UniqueConstraint(
            "source", "external_id", name="uq_job_source_external_id"
        ),
    )
