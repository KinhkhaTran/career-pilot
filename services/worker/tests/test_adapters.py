"""
Tests for ATS adapter interfaces.

Phase 1 only tests that:
1. The abstract base class enforces the interface.
2. Concrete stub adapters raise NotImplementedError (not implemented yet).
3. No adapter contains submission, CAPTCHA, or credential code.
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

from app.adapters.ashby import AshbyAdapter
from app.adapters.base import ATSAdapter, RawJobPosting
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.lever import LeverAdapter


def test_greenhouse_is_ats_adapter() -> None:
    assert issubclass(GreenhouseAdapter, ATSAdapter)


def test_lever_is_ats_adapter() -> None:
    assert issubclass(LeverAdapter, ATSAdapter)


def test_ashby_is_ats_adapter() -> None:
    assert issubclass(AshbyAdapter, ATSAdapter)


@pytest.mark.asyncio
async def test_greenhouse_discover_not_implemented() -> None:
    adapter = GreenhouseAdapter(board_token="test")
    gen = adapter.discover_jobs("test-company")
    with pytest.raises(NotImplementedError):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_greenhouse_health_check_not_implemented() -> None:
    adapter = GreenhouseAdapter(board_token="test")
    with pytest.raises(NotImplementedError):
        await adapter.health_check()


@pytest.mark.asyncio
async def test_lever_discover_not_implemented() -> None:
    adapter = LeverAdapter(company_slug="test")
    gen = adapter.discover_jobs("test-company")
    with pytest.raises(NotImplementedError):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_lever_health_check_not_implemented() -> None:
    adapter = LeverAdapter(company_slug="test")
    with pytest.raises(NotImplementedError):
        await adapter.health_check()


@pytest.mark.asyncio
async def test_ashby_discover_not_implemented() -> None:
    adapter = AshbyAdapter(organization_id="test")
    gen = adapter.discover_jobs("test-company")
    with pytest.raises(NotImplementedError):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_ashby_health_check_not_implemented() -> None:
    adapter = AshbyAdapter(organization_id="test")
    with pytest.raises(NotImplementedError):
        await adapter.health_check()


def test_no_captcha_or_submit_in_adapter_sources() -> None:
    """Verify no forbidden patterns exist in adapter source code."""
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
            assert pattern not in src, f"Forbidden pattern '{pattern}' found in {module.__name__}"


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
