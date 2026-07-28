from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_profiles_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/profiles")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_profile_not_found(client: AsyncClient) -> None:
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/profiles/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_profile_versions_not_found(client: AsyncClient) -> None:
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/profiles/{fake_id}/versions")
    assert resp.status_code == 404
