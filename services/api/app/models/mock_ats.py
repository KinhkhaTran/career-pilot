from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MockAtsSubmission(Base):
    """
    Receipt table for the in-process mock ATS sandbox.

    SAFETY: this table only ever records submissions delivered to the local
    `mock-ats://` sandbox board that ships with CareerPilot. It is never used for
    a real employer destination, and recording a row here does not advance the
    application state machine past `stopped_before_submit`.
    """

    __tablename__ = "mock_ats_submissions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    board_token: Mapped[str] = mapped_column(String(128), nullable=False)
    external_job_id: Mapped[str] = mapped_column(String(256), nullable=False)
    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    browser_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    confirmation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    packet_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    # Replaying the same run + packet returns the original receipt instead of a duplicate
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)

    received_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_mock_ats_idempotency"),
    )
