"""
Abstract ATS adapter interface.

Phase 2 will implement Greenhouse, Lever, and Ashby adapters.
This file defines the interface that all adapters must implement.

Safety: Adapters in Phase 1 MUST NOT submit applications. They are
for discovery (reading public job postings) only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class RawJobPosting:
    external_id: str
    source: str
    source_url: str
    title: str
    company: str
    location: str | None
    is_remote: bool
    description: str
    raw_data: dict[str, object]


class ATSAdapter(ABC):
    """
    Abstract base for ATS job discovery adapters.

    Initial release boundary: READ-ONLY.
    Adapters fetch public job postings only. No login, no form submission,
    no CAPTCHA handling, no credential access.
    """

    source_name: str

    @abstractmethod
    def discover_jobs(self, company_id: str) -> AsyncIterator[RawJobPosting]:
        """
        Yield raw job postings from the ATS public API.
        Must respect robots.txt, rate limits, and terms of service.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the adapter can reach the ATS endpoint."""
        ...
