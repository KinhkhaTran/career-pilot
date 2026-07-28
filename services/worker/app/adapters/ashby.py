"""
Ashby ATS adapter — Phase 2 stub.

Full implementation is deferred to Phase 2 (Job Discovery).
This file defines the concrete class signature for Ashby's
public job board posting API (no authentication required for public listings).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import ATSAdapter, RawJobPosting


class AshbyAdapter(ATSAdapter):
    """
    Reads public Ashby job board postings.
    API: https://api.ashbyhq.com/posting-api/job-board/{organization_id}
    No credentials required for public listings.
    """

    source_name = "ashby"
    _BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, organization_id: str) -> None:
        self.organization_id = organization_id

    async def discover_jobs(self, company_id: str) -> AsyncIterator[RawJobPosting]:
        """Phase 2: will call Ashby public job board API."""
        raise NotImplementedError("Ashby adapter is implemented in Phase 2")
        yield  # makes this an async generator

    async def health_check(self) -> bool:
        """Phase 2: will verify Ashby organization endpoint is reachable."""
        raise NotImplementedError("Ashby adapter is implemented in Phase 2")
