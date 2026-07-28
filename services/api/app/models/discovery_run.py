from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DiscoveryRun(Base):
    """
    Tracks a single scheduled or manual job-discovery run for one ATS source.

    An idempotency_key prevents duplicate runs from being enqueued.
    Counts are updated as the run progresses; status transitions are:
      pending → running → completed | failed
    """

    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    jobs_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    events: Mapped[list[DiscoveryRunEvent]] = relationship(
        "DiscoveryRunEvent",
        back_populates="run",
        order_by="DiscoveryRunEvent.created_at",
    )


class DiscoveryRunEvent(Base):
    """
    Immutable append-only audit record for discovery run milestones.

    Rows are never updated or deleted. The `detail` JSON carries
    event-specific payload (counts, error messages, batch info).
    """

    __tablename__ = "discovery_run_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    discovery_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[DiscoveryRun] = relationship("DiscoveryRun", back_populates="events")
