from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Application(Base):
    """
    Tracks a candidate's application lifecycle for a single job.

    The `status` field is always managed through the state machine —
    never written directly. The `packet_fingerprint` JSON captures the
    exact versions of résumé, answers, and cover-letter that were approved.
    """

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    candidate_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    # Current state — managed exclusively via the state machine
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")

    # Snapshot of approved packet: { profile_version, resume_version, answer_versions, ... }
    packet_fingerprint: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationship to the immutable audit log
    events: Mapped[list[ApplicationEvent]] = relationship(
        "ApplicationEvent", back_populates="application", order_by="ApplicationEvent.created_at"
    )


class ApplicationEvent(Base):
    """
    Immutable append-only audit record for every state transition.

    INVARIANTS:
    - Rows are never updated or deleted.
    - `to_status` is always set; `from_status` is null for the initial creation event.
    - `triggered_by` is either 'system' or 'human'.
    """

    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_status: Mapped[str] = mapped_column(String(64), nullable=False)

    # Who or what triggered the transition
    triggered_by: Mapped[str] = mapped_column(String(16), nullable=False)  # 'system' | 'human'
    actor_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Immutable creation timestamp only — no updated_at
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application: Mapped[Application] = relationship("Application", back_populates="events")
