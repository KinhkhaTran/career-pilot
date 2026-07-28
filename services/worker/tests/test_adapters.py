"""
Tests for ATS adapter implementations.

Phase 2: tests use deterministic JSON fixtures via a mock httpx client.
No live network calls are made.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.ashby import AshbyAdapter
from app.adapters.base import ATSAdapter, RawJobPosting, RetryExhaustedError
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.lever import LeverAdapter

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "mock-ats"


def _mock_client(fixture_name: str, status_code: int = 200) -> httpx.AsyncClient:
    """Return a mock AsyncClient that responds with the given fixture."""
    fixture_path = _FIXTURES / fixture_name
    payload = json.loads(fixture_path.read_text())

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.json.return_value = payload
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response
    mock_client.head.return_value = mock_response
    return mock_client  # type: ignore[return-value]


def _mock_error_client(exc: Exception) -> httpx.AsyncClient:
    """Return a mock client that raises the given exception on every call."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = exc
    mock_client.head.side_effect = exc
    return mock_client  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Subclass checks
# ---------------------------------------------------------------------------


def test_greenhouse_is_ats_adapter() -> None:
    assert issubclass(GreenhouseAdapter, ATSAdapter)


def test_lever_is_ats_adapter() -> None:
    assert issubclass(LeverAdapter, ATSAdapter)


def test_ashby_is_ats_adapter() -> None:
    assert issubclass(AshbyAdapter, ATSAdapter)


# ---------------------------------------------------------------------------
# RawJobPosting immutability
# ---------------------------------------------------------------------------


def test_raw_job_posting_is_frozen() -> None:
    posting = RawJobPosting(
        external_id="abc",
        source="greenhouse",
        source_url="https://example.com/jobs/abc",
        title="Engineer",
        company="Acme",
        location="Remote",
        is_remote=True,
        description="...",
        raw_data={},
    )
    with pytest.raises(FrozenInstanceError):
        posting.external_id = "xyz"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Greenhouse adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_greenhouse_discover_jobs_from_fixture() -> None:
    client = _mock_client("greenhouse.json")
    adapter = GreenhouseAdapter(board_token="acmecorp", client=client)

    postings = [p async for p in adapter.discover_jobs()]

    assert len(postings) == 3
    assert all(p.source == "greenhouse" for p in postings)
    assert all(p.external_id for p in postings)
    assert all(p.title for p in postings)


@pytest.mark.asyncio
async def test_greenhouse_posting_fields() -> None:
    client = _mock_client("greenhouse.json")
    adapter = GreenhouseAdapter(board_token="acmecorp", client=client)

    postings = [p async for p in adapter.discover_jobs()]
    first = postings[0]

    assert first.external_id == "4001001"
    assert "Senior Software Engineer" in first.title
    assert first.source_url.startswith("https://boards.greenhouse.io")
    assert first.company == "acmecorp"


@pytest.mark.asyncio
async def test_greenhouse_health_check_ok() -> None:
    client = _mock_client("greenhouse.json", status_code=200)
    adapter = GreenhouseAdapter(board_token="acmecorp", client=client)
    assert await adapter.health_check() is True


@pytest.mark.asyncio
async def test_greenhouse_health_check_network_error() -> None:
    client = _mock_error_client(httpx.NetworkError("connection refused"))
    adapter = GreenhouseAdapter(board_token="acmecorp", client=client)
    assert await adapter.health_check() is False


@pytest.mark.asyncio
async def test_greenhouse_retry_exhausted_on_network_error() -> None:
    client = _mock_error_client(httpx.NetworkError("unreachable"))
    adapter = GreenhouseAdapter(board_token="acmecorp", client=client)
    with pytest.raises(RetryExhaustedError):
        async for _ in adapter.discover_jobs():
            pass


# ---------------------------------------------------------------------------
# Lever adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lever_discover_jobs_from_fixture() -> None:
    client = _mock_client("lever.json")
    adapter = LeverAdapter(company_slug="nexuslabs", client=client)

    postings = [p async for p in adapter.discover_jobs()]

    assert len(postings) == 3
    assert all(p.source == "lever" for p in postings)


@pytest.mark.asyncio
async def test_lever_posting_fields() -> None:
    client = _mock_client("lever.json")
    adapter = LeverAdapter(company_slug="nexuslabs", client=client)

    postings = [p async for p in adapter.discover_jobs()]
    first = postings[0]

    assert first.external_id == "lever-posting-uuid-0001"
    assert "Backend Engineer" in first.title
    assert first.source_url.startswith("https://jobs.lever.co")
    assert first.location == "Remote"


@pytest.mark.asyncio
async def test_lever_health_check_ok() -> None:
    client = _mock_client("lever.json", status_code=200)
    adapter = LeverAdapter(company_slug="nexuslabs", client=client)
    assert await adapter.health_check() is True


@pytest.mark.asyncio
async def test_lever_retry_exhausted_on_timeout() -> None:
    client = _mock_error_client(httpx.TimeoutException("timed out"))
    adapter = LeverAdapter(company_slug="nexuslabs", client=client)
    with pytest.raises(RetryExhaustedError):
        async for _ in adapter.discover_jobs():
            pass


# ---------------------------------------------------------------------------
# Ashby adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ashby_discover_jobs_from_fixture() -> None:
    client = _mock_client("ashby.json")
    adapter = AshbyAdapter(organization_id="orbittech", client=client)

    postings = [p async for p in adapter.discover_jobs()]

    assert len(postings) == 3
    assert all(p.source == "ashby" for p in postings)


@pytest.mark.asyncio
async def test_ashby_posting_fields() -> None:
    client = _mock_client("ashby.json")
    adapter = AshbyAdapter(organization_id="orbittech", client=client)

    postings = [p async for p in adapter.discover_jobs()]
    first = postings[0]

    assert first.external_id == "ashby-job-uuid-0001"
    assert "Staff Software Engineer" in first.title
    assert first.is_remote is True
    assert first.location == "Remote"


@pytest.mark.asyncio
async def test_ashby_health_check_ok() -> None:
    client = _mock_client("ashby.json", status_code=200)
    adapter = AshbyAdapter(organization_id="orbittech", client=client)
    assert await adapter.health_check() is True


@pytest.mark.asyncio
async def test_ashby_retry_exhausted_on_server_error() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=mock_response
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = AshbyAdapter(organization_id="orbittech", client=mock_client)  # type: ignore[arg-type]
    with pytest.raises(RetryExhaustedError):
        async for _ in adapter.discover_jobs():
            pass


# ---------------------------------------------------------------------------
# Safety scan — no forbidden patterns in adapter source code
# ---------------------------------------------------------------------------


def test_no_captcha_or_submit_in_adapter_sources() -> None:
    import app.adapters.ashby as ab
    import app.adapters.greenhouse as gh
    import app.adapters.lever as lv

    forbidden = [
        "captcha",
        "bypass",
        "auto_submit",
        "inbox_code",
        "proxy_rotate",
        "password",
    ]
    for module in [gh, lv, ab]:
        src = inspect.getsource(module).lower()
        for pattern in forbidden:
            assert pattern not in src, f"Forbidden pattern {pattern!r} found in {module.__name__}"


def test_no_captcha_in_discovery_module() -> None:
    import app.queues.discovery as disc

    src = inspect.getsource(disc).lower()
    for pattern in ["captcha", "proxy_rotate", "bypass", "auto_submit"]:
        assert pattern not in src
