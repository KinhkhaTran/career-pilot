"""
Greenhouse ATS adapter — Phase 2 stub.

Full implementation is deferred to Phase 2 (Job Discovery).
This file defines the concrete class signature for Greenhouse's
public Job Board API (no authentication required for public listings).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import ATSAdapter, RawJobPosting


class GreenhouseAdapter(ATSAdapter):
    """
    Reads public Greenhouse job board postings.
    API: https://boards-api.greenhouse.io/v1/boards/{token}/jobs
    No credentials required for public boards.
    """

    source_name = "greenhouse"
    _BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, board_token: str) -> None:
        self.board_token = board_token

    async def discover_jobs(self, company_id: str) -> AsyncIterator[RawJobPosting]:
        """Phase 2: will call Greenhouse public API."""
        raise NotImplementedError("Greenhouse adapter is implemented in Phase 2")
        yield  # makes this an async generator

    async def health_check(self) -> bool:
        """Phase 2: will verify Greenhouse board token is reachable."""
        raise NotImplementedError("Greenhouse adapter is implemented in Phase 2")
