from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DiscoveryRunEventSchema(BaseModel):
    id: str
    discovery_run_id: str
    event_type: str
    detail: dict[str, object] = {}
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DiscoveryRunSchema(BaseModel):
    id: str
    source: str
    company_id: str
    status: str
    idempotency_key: str
    jobs_discovered: int = 0
    jobs_upserted: int = 0
    jobs_skipped: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    events: list[DiscoveryRunEventSchema] = []

    model_config = {"from_attributes": True}


class DiscoveryRunSummarySchema(BaseModel):
    id: str
    source: str
    company_id: str
    status: str
    jobs_discovered: int = 0
    jobs_upserted: int = 0
    jobs_skipped: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
