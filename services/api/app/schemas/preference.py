from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.matching.engine import MatchConstraints


class PreferenceWriteSchema(BaseModel):
    """Payload for saving a candidate's search preferences."""

    remote_only: bool = False
    allowed_locations: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    min_salary: int | None = Field(default=None, ge=0)


class PreferenceSchema(PreferenceWriteSchema):
    candidate_profile_id: str
    version: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

    def constraints(self) -> MatchConstraints:
        """Project the stored preferences onto the matching engine's hard constraints."""
        return MatchConstraints(
            remote_only=self.remote_only,
            allowed_locations=self.allowed_locations,
            employment_types=self.employment_types,
        )
