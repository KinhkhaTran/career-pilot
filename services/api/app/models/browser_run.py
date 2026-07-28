from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class BrowserRun(Base):
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
    # Token-gated submission (ADR 0008); all default to the safe, non-submitting state.
    final_page_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted: Mapped[bool] = mapped_column(nullable=False, default=False)
    confirmation: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    submission_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="stop_before_submit")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    steps: Mapped[list[BrowserRunStep]] = relationship("BrowserRunStep", back_populates="run", order_by="BrowserRunStep.sequence", cascade="all, delete-orphan")
    events: Mapped[list[BrowserRunEvent]] = relationship("BrowserRunEvent", back_populates="run", order_by="BrowserRunEvent.sequence", cascade="all, delete-orphan")
    screenshots: Mapped[list[BrowserScreenshot]] = relationship("BrowserScreenshot", back_populates="run", order_by="BrowserScreenshot.sequence", cascade="all, delete-orphan")


class ApprovalToken(Base):
    """A single-use authorization to click Submit once, bound to an exact state.

    The token *string* itself is never stored — only its id, the HMAC binding
    digest, and the immutable facts it was minted against. ``consumed`` flips to
    True the moment the worker uses it, so a submission can never be replayed.
    """

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
