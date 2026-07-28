from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.state_machine.application import ApplicationStatus


class ApplicationEventSchema(BaseModel):
    """Immutable audit event for a state transition."""

    id: str
    application_id: str
    from_status: str | None = None
    to_status: str
    triggered_by: str  # "system" | "human"
    actor_id: str | None = None
    note: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PacketFingerprintSchema(BaseModel):
    """Captures the exact approved versions that constitute a submission packet."""

    profile_version: int
    resume_version: int | None = None
    cover_letter_version: int | None = None
    answer_versions: dict[str, int] = Field(default_factory=dict)
    job_snapshot_hash: str
    packet_hash: str


class ApplicationSchema(BaseModel):
    """Full application including audit event history."""

    id: str
    job_id: str
    candidate_profile_id: str
    status: str
    packet_fingerprint: PacketFingerprintSchema | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    events: list[ApplicationEventSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApplicationSummarySchema(BaseModel):
    """Lightweight application for list views."""

    id: str
    job_id: str
    candidate_profile_id: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TransitionRequestSchema(BaseModel):
    """Request body for the POST /applications/{id}/transition endpoint."""

    target_status: ApplicationStatus
    note: str | None = None
