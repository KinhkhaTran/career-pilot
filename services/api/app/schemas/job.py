from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SalaryRangeSchema(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "USD"
    period: str = "yearly"  # "yearly" | "monthly" | "hourly"


class JobSchema(BaseModel):
    """Full job posting schema matching the TypeScript Job type."""

    id: str
    external_id: str
    source: str
    source_url: str
    title: str
    company: str
    location: str | None = None
    is_remote: bool = False
    employment_type: str | None = None
    salary_range: SalaryRangeSchema | None = None
    description: str
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    status: str = "discovered"
    snapshot_hash: str
    discovered_at: datetime | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    normalized_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobSummarySchema(BaseModel):
    """Lightweight job schema for list views."""

    id: str
    title: str
    company: str
    location: str | None = None
    is_remote: bool = False
    employment_type: str | None = None
    status: str
    source: str
    discovered_at: datetime | None = None
    posted_at: datetime | None = None

    model_config = {"from_attributes": True}
