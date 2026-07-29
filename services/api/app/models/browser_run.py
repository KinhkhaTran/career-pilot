from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class BrowserRun(Base):
    """
    An approval-bound assisted run.

    `mode` distinguishes the two execution boundaries:
      - ``mock_sandbox``: a deterministic autofill against the in-process mock ATS
        board. Executed step-by-step by the API so a human can watch, pause, and
        resume it. Never touches an employer URL.
      - ``operator_browser``: a visible Playwright page supplied by an operator and
        driven by the isolated worker. Still has no submit action.

    `plan` plus `cursor` are the persisted run state: pausing simply stops
    advancing the cursor, and resuming continues from the same recorded position.
    """

    __tablename__ = "browser_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    packet_fingerprint: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    immutable_inputs: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    approved_fields: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    headless: Mapped[bool] = mapped_column(nullable=False, default=False)
    adapter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stopped_before_submit: Mapped[bool] = mapped_column(nullable=False, default=False)
    final_page_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted: Mapped[bool] = mapped_column(nullable=False, default=False)
    confirmation: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    submission_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="stop_before_submit")

    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="mock_sandbox")
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="mock_ats")
    target_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    plan: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paused_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    steps: Mapped[list[BrowserRunStep]] = relationship("BrowserRunStep", back_populates="run", order_by="BrowserRunStep.sequence", cascade="all, delete-orphan")
    events: Mapped[list[BrowserRunEvent]] = relationship("BrowserRunEvent", back_populates="run", order_by="BrowserRunEvent.sequence", cascade="all, delete-orphan")
    screenshots: Mapped[list[BrowserScreenshot]] = relationship("BrowserScreenshot", back_populates="run", order_by="BrowserScreenshot.sequence", cascade="all, delete-orphan")


class ApprovalToken(Base):
    """Single-use authorization record bound to an exact supervised run state."""

    __tablename__ = "approval_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    browser_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("browser_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    token_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_set_version: Mapped[int] = mapped_column(Integer, nullable=False)
    final_page_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    consumed: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    consumed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

class BrowserRunStep(Base):
    __tablename__ = "browser_run_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("browser_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    run: Mapped[BrowserRun] = relationship("BrowserRun", back_populates="steps")


class BrowserRunEvent(Base):
    __tablename__ = "browser_run_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("browser_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    run: Mapped[BrowserRun] = relationship("BrowserRun", back_populates="events")


class BrowserScreenshot(Base):
    __tablename__ = "browser_screenshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("browser_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    run: Mapped[BrowserRun] = relationship("BrowserRun", back_populates="screenshots")
