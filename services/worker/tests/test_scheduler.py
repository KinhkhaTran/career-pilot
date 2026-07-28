"""
Tests for the scheduled discovery + auto-match orchestration.

The scheduler logic is exercised with discover_source and the match-refresh
trigger mocked, so no network or real database is required. get_enabled_sources
is verified against an in-memory SQLite database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import _metadata, discovery_sources_table, get_enabled_sources
from app.queues.scheduler import scheduled_discovery, trigger_match_refresh


@pytest.mark.asyncio
async def test_get_enabled_sources_returns_only_enabled_oldest_first() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_metadata.create_all)
        await conn.execute(
            discovery_sources_table.insert(),
            [
                {
                    "id": "1", "source": "greenhouse", "company_id": "figma", "label": "Figma",
                    "enabled": True, "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                },
                {
                    "id": "2", "source": "lever", "company_id": "acme", "label": "Acme",
                    "enabled": False, "created_at": datetime(2026, 1, 2, tzinfo=UTC),
                },
                {
                    "id": "3", "source": "greenhouse", "company_id": "gitlab", "label": "GitLab",
                    "enabled": True, "created_at": datetime(2026, 1, 3, tzinfo=UTC),
                },
            ],
        )
        sources = await get_enabled_sources(conn)
    await engine.dispose()

    assert [s["company_id"] for s in sources] == ["figma", "gitlab"]
    assert all(s["source"] == "greenhouse" for s in sources)


def _patch_sources(sources: list[dict[str, str]]) -> AsyncMock:
    return AsyncMock(return_value=sources)


@pytest.mark.asyncio
async def test_scheduled_discovery_aggregates_and_triggers_match() -> None:
    sources = [
        {"source": "greenhouse", "company_id": "figma", "label": "Figma"},
        {"source": "greenhouse", "company_id": "gitlab", "label": "GitLab"},
    ]
    discover = AsyncMock(side_effect=[
        {"discovered": 5, "upserted": 5, "skipped": 0},
        {"discovered": 3, "upserted": 2, "skipped": 1},
    ])
    refresh = AsyncMock(return_value={"created": 8, "profiles": 1})

    with patch("app.queues.scheduler.get_enabled_sources", _patch_sources(sources)), \
         patch("app.queues.scheduler.get_connection"), \
         patch("app.queues.scheduler.discover_source", discover), \
         patch("app.queues.scheduler.trigger_match_refresh", refresh):
        summary = await scheduled_discovery({})

    assert summary["sources"] == 2
    assert summary["discovered"] == 8
    assert summary["upserted"] == 7
    assert summary["failures"] == 0
    assert summary["matched"] is True
    assert discover.await_count == 2
    refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduled_discovery_resilient_to_one_source_failure() -> None:
    sources = [
        {"source": "greenhouse", "company_id": "figma", "label": "Figma"},
        {"source": "greenhouse", "company_id": "broken", "label": "Broken"},
    ]
    discover = AsyncMock(side_effect=[
        {"discovered": 5, "upserted": 5, "skipped": 0},
        RuntimeError("boom"),
    ])
    refresh = AsyncMock(return_value={"created": 5})

    with patch("app.queues.scheduler.get_enabled_sources", _patch_sources(sources)), \
         patch("app.queues.scheduler.get_connection"), \
         patch("app.queues.scheduler.discover_source", discover), \
         patch("app.queues.scheduler.trigger_match_refresh", refresh):
        summary = await scheduled_discovery({})

    assert summary["failures"] == 1
    assert summary["discovered"] == 5
    # A failing source must not stop the cycle from matching what did land.
    refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduled_discovery_no_sources_skips_match() -> None:
    refresh = AsyncMock()
    with patch("app.queues.scheduler.get_enabled_sources", _patch_sources([])), \
         patch("app.queues.scheduler.get_connection"), \
         patch("app.queues.scheduler.trigger_match_refresh", refresh):
        summary = await scheduled_discovery({})

    assert summary["sources"] == 0
    assert summary["matched"] is False
    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_match_refresh_returns_none_when_api_unreachable() -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("refused")

    with patch("httpx.AsyncClient.post", side_effect=_raise):
        assert await trigger_match_refresh() is None
