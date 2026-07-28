"""Tests for discovery run API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery_run import DiscoveryRun, DiscoveryRunEvent


def _run_id(n: int) -> str:
    return str(uuid.UUID(f"00000000-0000-0000-0007-{str(n).zfill(12)}"))


def _evt_id(n: int) -> str:
    return str(uuid.UUID(f"00000000-0000-0000-0008-{str(n).zfill(12)}"))


async def _seed_run(db: AsyncSession, run_id: str, **kwargs: object) -> DiscoveryRun:
    run = DiscoveryRun(
        id=run_id,
        source=kwargs.get("source", "greenhouse"),
        company_id=kwargs.get("company_id", "acme"),
        status=kwargs.get("status", "completed"),
        idempotency_key=kwargs.get("idempotency_key", f"key-{run_id}"),
        jobs_discovered=kwargs.get("jobs_discovered", 3),
        jobs_upserted=kwargs.get("jobs_upserted", 2),
        jobs_skipped=kwargs.get("jobs_skipped", 1),
    )
    db.add(run)
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_list_discovery_runs_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/discovery/runs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_discovery_runs_returns_runs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    run1 = await _seed_run(db_session, _run_id(1), source="greenhouse")
    run2 = await _seed_run(db_session, _run_id(2), source="lever", idempotency_key="key-lever-2")

    resp = await client.get("/api/v1/discovery/runs")
    assert resp.status_code == 200
    data = resp.json()
    ids = [r["id"] for r in data]
    assert run1.id in ids
    assert run2.id in ids


@pytest.mark.asyncio
async def test_list_discovery_runs_filter_by_source(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_run(db_session, _run_id(3), source="greenhouse", idempotency_key="key-gh-3")
    await _seed_run(db_session, _run_id(4), source="lever", idempotency_key="key-lv-4")

    resp = await client.get("/api/v1/discovery/runs?source=lever")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["source"] == "lever" for r in data)


@pytest.mark.asyncio
async def test_list_discovery_runs_filter_by_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_run(db_session, _run_id(5), status="running", idempotency_key="key-running-5")
    await _seed_run(db_session, _run_id(6), status="completed", idempotency_key="key-done-6")

    resp = await client.get("/api/v1/discovery/runs?status=running")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["status"] == "running" for r in data)


@pytest.mark.asyncio
async def test_get_discovery_run_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    run = await _seed_run(db_session, _run_id(7), idempotency_key="key-get-7")

    resp = await client.get(f"/api/v1/discovery/runs/{run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run.id
    assert data["source"] == run.source
    assert data["jobs_discovered"] == 3
    assert "events" in data


@pytest.mark.asyncio
async def test_get_discovery_run_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/discovery/runs/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_discovery_run_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    run = await _seed_run(db_session, _run_id(8), idempotency_key="key-evt-8")
    event = DiscoveryRunEvent(
        id=_evt_id(1),
        discovery_run_id=run.id,
        event_type="run_started",
        detail={"source": "greenhouse"},
    )
    db_session.add(event)
    await db_session.commit()

    resp = await client.get(f"/api/v1/discovery/runs/{run.id}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["event_type"] == "run_started"


@pytest.mark.asyncio
async def test_list_discovery_run_events_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/discovery/runs/{uuid.uuid4()}/events")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_discovery_run_summary_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_run(db_session, _run_id(9), idempotency_key="key-summary-9")

    resp = await client.get("/api/v1/discovery/runs")
    assert resp.status_code == 200
    item = resp.json()[0]

    assert "id" in item
    assert "source" in item
    assert "company_id" in item
    assert "status" in item
    assert "jobs_discovered" in item
    assert "jobs_upserted" in item
    assert "jobs_skipped" in item


@pytest.mark.asyncio
async def test_discovery_run_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    for i in range(10, 16):
        await _seed_run(db_session, _run_id(i), idempotency_key=f"key-page-{i}")

    resp = await client.get("/api/v1/discovery/runs?limit=3&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) <= 3
