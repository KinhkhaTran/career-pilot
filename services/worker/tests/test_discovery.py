"""
Tests for the discovery orchestration layer.

DB interactions are mocked so no real database is required.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.base import ATSAdapter, RawJobPosting, RetryExhaustedError
from app.adapters.normalizer import normalize


def _make_raw(ext_id: str = "job-001", source: str = "greenhouse") -> RawJobPosting:
    return RawJobPosting(
        external_id=ext_id,
        source=source,
        source_url=f"https://example.com/jobs/{ext_id}",
        title="Senior Engineer",
        company="Acme",
        location="Remote",
        is_remote=True,
        description="<p>Join us as an engineer.</p>",
        raw_data={},
    )


class FakeAdapter(ATSAdapter):
    """Test double that yields controlled RawJobPosting items."""

    source_name = "greenhouse"

    def __init__(self, postings: list[RawJobPosting]) -> None:
        self._postings = postings

    async def discover_jobs(self) -> AsyncIterator[RawJobPosting]:  # type: ignore[override]
        for p in self._postings:
            yield p

    async def health_check(self) -> bool:
        return True


class FailingAdapter(ATSAdapter):
    """Test double that raises RetryExhaustedError."""

    source_name = "greenhouse"

    def __init__(self) -> None:
        pass

    async def discover_jobs(self) -> AsyncIterator[RawJobPosting]:  # type: ignore[override]
        raise RetryExhaustedError("greenhouse", "https://example.com", 3)
        yield  # make it a generator

    async def health_check(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_run_discovery_completes_successfully() -> None:
    postings = [_make_raw("job-001"), _make_raw("job-002"), _make_raw("job-003")]
    adapter = FakeAdapter(postings)
    run_id = "run-001"

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.queues.discovery.get_connection") as mock_get_conn,
        patch("app.queues.discovery.update_discovery_run_status"),
        patch("app.queues.discovery.append_discovery_event") as mock_event,
        patch("app.queues.discovery.upsert_job", return_value="upserted"),
    ):
        mock_get_conn.return_value = mock_conn

        from app.queues.discovery import run_discovery

        counts = await run_discovery(adapter, run_id)

    assert counts["discovered"] == 3
    assert counts["upserted"] == 3
    assert counts["skipped"] == 0

    # run_started and run_completed events should be appended
    event_types = [call.args[2] for call in mock_event.call_args_list]
    assert "run_started" in event_types
    assert "run_completed" in event_types


@pytest.mark.asyncio
async def test_run_discovery_counts_skipped() -> None:
    postings = [_make_raw("job-001"), _make_raw("job-002")]
    adapter = FakeAdapter(postings)
    run_id = "run-002"

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.queues.discovery.get_connection") as mock_get_conn,
        patch("app.queues.discovery.update_discovery_run_status"),
        patch("app.queues.discovery.append_discovery_event"),
        patch("app.queues.discovery.upsert_job", return_value="skipped"),
    ):
        mock_get_conn.return_value = mock_conn

        from app.queues.discovery import run_discovery

        counts = await run_discovery(adapter, run_id)

    assert counts["skipped"] == 2
    assert counts["upserted"] == 0


@pytest.mark.asyncio
async def test_run_discovery_marks_failed_on_retry_exhausted() -> None:
    adapter = FailingAdapter()
    run_id = "run-003"

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.queues.discovery.get_connection") as mock_get_conn,
        patch("app.queues.discovery.update_discovery_run_status") as mock_update,
        patch("app.queues.discovery.append_discovery_event") as mock_event,
        patch("app.queues.discovery.upsert_job"),
    ):
        mock_get_conn.return_value = mock_conn

        from app.queues.discovery import run_discovery

        with pytest.raises(RetryExhaustedError):
            await run_discovery(adapter, run_id)

    # Should record failed status
    update_calls = mock_update.call_args_list
    failed_call = next((c for c in update_calls if c.kwargs.get("status") == "failed"), None)
    assert failed_call is not None

    event_types = [call.args[2] for call in mock_event.call_args_list]
    assert "run_failed" in event_types


@pytest.mark.asyncio
async def test_run_discovery_empty_source() -> None:
    adapter = FakeAdapter([])
    run_id = "run-004"

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.queues.discovery.get_connection") as mock_get_conn,
        patch("app.queues.discovery.update_discovery_run_status"),
        patch("app.queues.discovery.append_discovery_event"),
        patch("app.queues.discovery.upsert_job"),
    ):
        mock_get_conn.return_value = mock_conn

        from app.queues.discovery import run_discovery

        counts = await run_discovery(adapter, run_id)

    assert counts["discovered"] == 0
    assert counts["upserted"] == 0
    assert counts["skipped"] == 0


def test_normalize_greenhouse_raw() -> None:
    raw = _make_raw("job-001", "greenhouse")
    result = normalize(raw)
    assert result.source == "greenhouse"
    assert result.is_remote is True
    assert len(result.snapshot_hash) == 64
    assert "<p>" not in result.description
