"""
Ashby ATS adapter — public read-only job board discovery.

API: GET https://api.ashbyhq.com/posting-api/job-board/{organization_id}
No authentication required for public job boards.
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


class AshbyAdapter(ATSAdapter):
    """
    Reads public Ashby job board postings.

    Yields one RawJobPosting per listing. HTML description is preserved
    in RawJobPosting.description for later normalization.
    No login, no cookies, no verification-workaround logic.
    """

    source_name = "ashby"
    _BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, organization_id: str, *, client: httpx.AsyncClient | None = None) -> None:
        self.organization_id = organization_id
        self._client = client

    def _make_url(self) -> str:
        return f"{self._BASE_URL}/{self.organization_id}"

    async def _fetch_with_retry(self, client: httpx.AsyncClient, url: str) -> dict[str, object]:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.get(url, timeout=_TIMEOUT_S)
                if response.status_code == 429:
                    wait = _BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning("Ashby rate-limited; waiting %.1fs (attempt %d)", wait, attempt)
                    await asyncio.sleep(wait)
                    continue
                if response.status_code >= 500:
                    wait = _BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning(
                        "Ashby server error %d; retrying in %.1fs (attempt %d)",
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
                result: dict[str, object] = response.json()
                return result
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                wait = _BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    "Ashby network error (%s); retrying in %.1fs (attempt %d)",
                    exc,
                    wait,
                    attempt,
                )
                await asyncio.sleep(wait)
                last_exc = exc
        raise RetryExhaustedError(self.source_name, url, _MAX_RETRIES) from last_exc

    async def discover_jobs(self) -> AsyncIterator[RawJobPosting]:
        url = self._make_url()
        logger.info("Ashby discovery started: org=%r url=%r", self.organization_id, url)

        async def _run(client: httpx.AsyncClient) -> AsyncIterator[RawJobPosting]:
            data = await self._fetch_with_retry(client, url)
            jobs = data.get("jobs", [])
            if not isinstance(jobs, list):
                logger.warning("Ashby: unexpected jobs payload type %r", type(jobs))
                return

            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_id = job.get("id")
                title = job.get("title", "")
                job_url = job.get("jobUrl", "")
                location = job.get("location") or None
                is_remote = bool(job.get("isRemote", False))
                description = job.get("descriptionHtml", "") or ""

                if not job_id or not title:
                    logger.debug("Ashby: skipping job with missing id or title: %r", job)
                    continue

                raw_data: dict[str, object] = dict(job)
                published_at = job.get("publishedAt")
                if isinstance(published_at, str):
                    raw_data["posted_at"] = published_at

                yield RawJobPosting(
                    external_id=str(job_id),
                    source=self.source_name,
                    source_url=str(job_url),
                    title=str(title),
                    company=self.organization_id,
                    location=location,
                    is_remote=is_remote,
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
        url = self._make_url()
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
