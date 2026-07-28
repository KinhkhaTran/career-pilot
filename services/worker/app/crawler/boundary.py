"""
Generic crawler boundary interface.

Defines the Protocol that a Crawl4AI-compatible generic crawler adapter must
satisfy. No dependency on Crawl4AI or any browser automation library is
introduced in Phase 2. This boundary contract exists so that Phase 5+ can
add a generic adapter without changing existing code.

Safety boundary: No browser automation, CAPTCHA solving, credential handling,
or proxy rotation is permitted. Crawlers must only fetch publicly accessible
URLs and must respect robots.txt and rate limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CrawlResult:
    """The result of fetching a single URL via the generic crawler boundary."""

    url: str
    content: str
    status_code: int
    content_type: str = "text/html"
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


@runtime_checkable
class CrawlerBoundary(Protocol):
    """
    Protocol for a generic URL fetcher compatible with Crawl4AI's interface.

    Implementations must:
    - Only fetch publicly accessible URLs (no authentication, no cookies).
    - Respect robots.txt and platform rate limits.
    - Use bounded timeouts and retries.
    - Never attempt CAPTCHA solving or browser fingerprint spoofing.

    Phase 2 does not wire any concrete implementation; this boundary
    exists as a forward-compatible contract for Phase 5+.
    """

    async def fetch(
        self,
        url: str,
        *,
        timeout_s: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> CrawlResult:
        """
        Fetch a single public URL and return its content.

        Raises:
            CrawlerFetchError: if the URL is unreachable after retries.
            CrawlerRateLimitError: if the server returns 429.
        """
        ...


class CrawlerError(Exception):
    """Base class for crawler boundary errors."""


class CrawlerFetchError(CrawlerError):
    """Raised when a URL cannot be fetched after retries."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"Failed to fetch {url!r}: {reason}")
        self.url = url
        self.reason = reason


class CrawlerRateLimitError(CrawlerError):
    """Raised when the server signals rate limiting (HTTP 429)."""

    def __init__(self, url: str, retry_after: int | None = None) -> None:
        msg = f"Rate limited fetching {url!r}"
        if retry_after is not None:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)
        self.url = url
        self.retry_after = retry_after
