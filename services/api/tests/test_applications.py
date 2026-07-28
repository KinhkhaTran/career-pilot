from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_applications_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/applications")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_application_not_found(client: AsyncClient) -> None:
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/applications/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_transition_application_not_found(client: AsyncClient) -> None:
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/applications/{fake_id}/transition",
        json={"target_status": "matched"},
    )
    assert resp.status_code == 404
