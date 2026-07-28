from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.matching.engine import MatchConstraints


class MatchSchema(BaseModel):
    id: str
    job_id: str
    candidate_profile_id: str
    profile_version: int
    input_fingerprint: str
    eligible: bool
    score: float
    reasons: list[str] = Field(default_factory=list)
    explanation: dict[str, Any]
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MatchRefreshSchema(BaseModel):
    profile_id: str
    profile_version: int | None = Field(default=None, ge=1)
    job_ids: list[str] | None = None
    constraints: MatchConstraints = Field(default_factory=MatchConstraints)


class MatchRefreshResponse(BaseModel):
    created: int
    existing: int
    matches: list[MatchSchema]


class ProfileRefreshSummary(BaseModel):
    profile_id: str
    profile_version: int
    created: int
    existing: int


class MatchRefreshAllResponse(BaseModel):
    """Summary of a match refresh across every candidate profile."""

    profiles: int
    jobs: int
    created: int
    existing: int
    per_profile: list[ProfileRefreshSummary]
