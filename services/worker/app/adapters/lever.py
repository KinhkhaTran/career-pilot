"""
Lever ATS adapter — Phase 2 stub.

Full implementation is deferred to Phase 2 (Job Discovery).
This file defines the concrete class signature for Lever's
public postings API (no authentication required for public listings).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import ATSAdapter, RawJobPosting


class LeverAdapter(ATSAdapter):
    """
    Reads public Lever job postings.
    API: https://api.lever.co/v0/postings/{company}
    No credentials required for public listings.
    """

    source_name = "lever"
    _BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, company_slug: str) -> None:
        self.company_slug = company_slug

    async def discover_jobs(self, company_id: str) -> AsyncIterator[RawJobPosting]:
        """Phase 2: will call Lever public postings API."""
        raise NotImplementedError("Lever adapter is implemented in Phase 2")
        yield  # makes this an async generator

    async def health_check(self) -> bool:
        """Phase 2: will verify Lever company endpoint is reachable."""
        raise NotImplementedError("Lever adapter is implemented in Phase 2")
