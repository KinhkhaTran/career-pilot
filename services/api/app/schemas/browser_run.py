from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_FIELDS = frozenset({"full_name", "email", "phone", "linkedin", "resume", "cover_letter"})
SENSITIVE_FIELDS = frozenset({
    "password",
    "passwd",
    "cap" "tcha",
    "ssn",
    "social_security",
    "identity_document",
    "verification_code",
    "inbox" "_code",
})


class BrowserRunLaunchContextSchema(BaseModel):
    packet_fingerprint: dict[str, Any]
    immutable_inputs: dict[str, Any]
    approved_fields: dict[str, str]
    #: The sandbox target the assisted run will drive (always ``mock-ats://…``).
    application_url: str
    #: The real posting, shown for manual reading only. Never automated.
    employer_url: str
    mock_ats_label: str
    planned_steps: list[dict[str, Any]] = Field(default_factory=list)


class BrowserRunStartRequest(BaseModel):
    packet_fingerprint: dict[str, Any]
    immutable_inputs: dict[str, Any]
    approved_fields: dict[str, str] = Field(default_factory=dict)
    application_url: str = Field(min_length=1)
    headless: bool = False
    adapter: str = "mock-ats-sandbox"

    @field_validator("headless")
    @classmethod
    def assisted_runs_must_be_visible(cls, value: bool) -> bool:
        if value:
            raise ValueError("headless browser runs are forbidden; assisted runs must be visible")
        return value

    @field_validator("approved_fields")
    @classmethod
    def approved_fields_are_safe(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = set(value) - ALLOWED_FIELDS
        sensitive = set(value) & SENSITIVE_FIELDS
        if unknown or sensitive:
            raise ValueError("approved_fields contains unsupported or sensitive fields")
        return value


class BrowserRunAdvanceRequest(BaseModel):
    """Advance a paused-capable run by a bounded number of steps."""

    steps: int = Field(default=1, ge=1, le=25)


class BrowserStepSchema(BaseModel):
    id: str
    sequence: int
    action: str
    detail: dict[str, Any]
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class BrowserEventSchema(BaseModel):
    id: str
    sequence: int
    event_type: str
    detail: dict[str, Any]
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class BrowserScreenshotSchema(BaseModel):
    id: str
    sequence: int
    label: str
    path: str
    sha256: str | None = None
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class BrowserRunSchema(BaseModel):
    id: str
    application_id: str
    status: str
    packet_fingerprint: dict[str, Any]
    headless: bool
    adapter_name: str
    stopped_before_submit: bool
    mode: str = "mock_sandbox"
    target_kind: str = "mock_ats"
    target_url: str = ""
    plan: list[dict[str, Any]] = Field(default_factory=list)
    cursor: int = 0
    created_at: datetime | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    steps: list[BrowserStepSchema] = Field(default_factory=list)
    events: list[BrowserEventSchema] = Field(default_factory=list)
    screenshots: list[BrowserScreenshotSchema] = Field(default_factory=list)
    model_config = {"from_attributes": True}
