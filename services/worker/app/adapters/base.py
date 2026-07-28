"""
Abstract ATS adapter interface and shared data types.

Safety: Adapters are READ-ONLY. They fetch public job postings only.
No login, no form submission, no CAPTCHA handling, no credential access.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RawJobPosting:
    """Minimally parsed job posting as returned by an ATS adapter."""

    external_id: str
    source: str
    source_url: str
    title: str
    company: str
    location: str | None
    is_remote: bool
    description: str
    raw_data: dict[str, object]


@dataclass(frozen=True)
class NormalizedJobData:
    """
    Fully normalized job posting ready for DB upsert.

    Produced by the normalizer; consumed by the discovery task.
    snapshot_hash is SHA-256(source|external_id|title|description).
    """

    external_id: str
    source: str
    source_url: str
    title: str
    company: str
    location: str | None
    is_remote: bool
    employment_type: str | None
    description: str
    requirements: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    snapshot_hash: str = ""
    posted_at: datetime | None = None
    salary_range: dict[str, object] | None = None


class ATSAdapter(ABC):
    """
    Abstract base for ATS job discovery adapters.

    Initial release boundary: READ-ONLY.
    Adapters fetch public job postings only. No login, no form submission,
    no CAPTCHA handling, no credential access, no proxy rotation.
    """

    source_name: str

    @abstractmethod
    def discover_jobs(self) -> AsyncIterator[RawJobPosting]:
        """
        Yield raw job postings from the ATS public API.

        Respects robots.txt, rate limits, and terms of service.
        Raises RetryExhaustedError after bounded retries on transient failures.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the adapter can reach the ATS endpoint."""
        ...


class RetryExhaustedError(Exception):
    """Raised when all retry attempts for an ATS request are exhausted."""

    def __init__(self, source: str, url: str, attempts: int) -> None:
        super().__init__(
            f"ATS request failed after {attempts} attempts: source={source!r} url={url!r}"
        )
        self.source = source
        self.url = url
        self.attempts = attempts
