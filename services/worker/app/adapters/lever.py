"""
Lever ATS adapter — public read-only job postings discovery.

API: GET https://api.lever.co/v0/postings/{company}?mode=json
No authentication required for public postings.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx

from .base import ATSAdapter, RawJobPosting, RetryExhaustedError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE_S = 2.0
_TIMEOUT_S = 30.0


class LeverAdapter(ATSAdapter):
    """
    Reads public Lever job postings.

    Yields one RawJobPosting per listing. The full Lever posting object
    is preserved in RawJobPosting.raw_data for later normalization.
    No login, no cookies, no verification-workaround logic.
    """

    source_name = "lever"
    _BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, company_slug: str, *, client: httpx.AsyncClient | None = None) -> None:
        self.company_slug = company_slug
        self._client = client

    def _make_url(self) -> str:
        return f"{self._BASE_URL}/{self.company_slug}?mode=json"

    async def _fetch_with_retry(self, client: httpx.AsyncClient, url: str) -> list[object]:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.get(url, timeout=_TIMEOUT_S)
                if response.status_code == 429:
                    wait = _BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning("Lever rate-limited; waiting %.1fs (attempt %d)", wait, attempt)
                    await asyncio.sleep(wait)
                    continue
                if response.status_code >= 500:
                    wait = _BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning(
                        "Lever server error %d; retrying in %.1fs (attempt %d)",
                        response.status_code,
                        wait,
                        attempt,
                    )
                    await asyncio.sleep(wait)
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response
                    )
                    continue
                response.raise_for_status()
                result: list[object] = response.json()
                return result
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                wait = _BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    "Lever network error (%s); retrying in %.1fs (attempt %d)",
                    exc,
                    wait,
                    attempt,
                )
                await asyncio.sleep(wait)
                last_exc = exc
        raise RetryExhaustedError(self.source_name, url, _MAX_RETRIES) from last_exc

    async def discover_jobs(self) -> AsyncIterator[RawJobPosting]:
        url = self._make_url()
        logger.info("Lever discovery started: company=%r url=%r", self.company_slug, url)

        async def _run(client: httpx.AsyncClient) -> AsyncIterator[RawJobPosting]:
            postings = await self._fetch_with_retry(client, url)
            if not isinstance(postings, list):
                logger.warning("Lever: unexpected response type %r", type(postings))
                return

            for posting in postings:
                if not isinstance(posting, dict):
                    continue
                job_id = posting.get("id")
                title = posting.get("text", "")
                urls_obj = posting.get("urls", {})
                show_url = ""
                if isinstance(urls_obj, dict):
                    show_url = urls_obj.get("show", "") or ""

                categories = posting.get("categories", {})
                location: str | None = None
                if isinstance(categories, dict):
                    location = categories.get("location") or None

                content_obj = posting.get("content", {})
                description = ""
                if isinstance(content_obj, dict):
                    description = (
                        content_obj.get("descriptionHtml") or content_obj.get("description") or ""
                    )

                if not job_id or not title:
                    logger.debug("Lever: skipping posting with missing id or text: %r", posting)
                    continue

                raw_data: dict[str, object] = dict(posting)
                created_at_ms = posting.get("createdAt")
                if isinstance(created_at_ms, int | float):
                    raw_data["posted_at"] = created_at_ms

                yield RawJobPosting(
                    external_id=str(job_id),
                    source=self.source_name,
                    source_url=str(show_url),
                    title=str(title),
                    company=self.company_slug,
                    location=location,
                    is_remote=False,
                    description=str(description),
                    raw_data=raw_data,
                )

        if self._client is not None:
            async for posting in _run(self._client):
                yield posting
        else:
            async with httpx.AsyncClient(
                headers={"User-Agent": "CareerPilot/2.0 (public job discovery; read-only)"}
            ) as client:
                async for posting in _run(client):
                    yield posting

    async def health_check(self) -> bool:
        url = f"{self._BASE_URL}/{self.company_slug}?limit=1&mode=json"
        try:
            if self._client is not None:
                resp = await self._client.get(url, timeout=10.0)
                return resp.status_code < 500
            else:
                async with httpx.AsyncClient(
                    headers={"User-Agent": "CareerPilot/2.0 (public job discovery; read-only)"}
                ) as client:
                    resp = await client.get(url, timeout=10.0)
                    return resp.status_code < 500
        except (httpx.TimeoutException, httpx.NetworkError):
            return False
