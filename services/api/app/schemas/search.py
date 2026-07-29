from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import JobSummarySchema
from app.schemas.match import MatchSchema
from app.schemas.preference import PreferenceSchema


class JobSearchRequest(BaseModel):
    """Run a preference-driven search over jobs already stored in the database."""

    profile_id: str
    profile_version: int | None = Field(default=None, ge=1)
    eligible_only: bool = True
    limit: int = Field(default=25, ge=1, le=200)


class SearchResultSchema(BaseModel):
    """One ranked job plus the persisted match that explains its score."""

    job: JobSummarySchema
    source_url: str
    match: MatchSchema


class JobSearchResponse(BaseModel):
    profile_id: str
    profile_version: int
    preferences: PreferenceSchema
    scanned: int
    filtered_out: int
    results: list[SearchResultSchema] = Field(default_factory=list)
