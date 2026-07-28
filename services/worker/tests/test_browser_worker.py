from __future__ import annotations

from pathlib import Path

import pytest

from app.browser_worker import AssistedApplicationWorker, GreenhouseLikeAdapter
from app.browser_worker.worker import BrowserRunRejected, BrowserRunRequest


class FakePage:
    def __init__(self) -> None:
        self.goto_urls: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.screenshots: list[str] = []

    async def goto(self, url: str) -> None:
        self.goto_urls.append(url)

    async def fill(self, selector: str, value: str) -> None:
        self.fills.append((selector, value))

    async def screenshot(self, *, path: str) -> bytes:
        self.screenshots.append(path)
        Path(path).write_bytes(b"fake screenshot")
        return b"fake screenshot"


def request(tmp_path: Path, **overrides: object) -> BrowserRunRequest:
    values: dict[str, object] = {
        "application_id": "app-1",
        "application_url": "https://jobs.invalid/apply/1",
        "packet_fingerprint": {"packet_hash": "packet-1"},
        "expected_packet_fingerprint": {"packet_hash": "packet-1"},
        "immutable_inputs": {
            "profile_version": 1,
            "job_snapshot_hash": "job-1",
            "job_snapshot": {"title": "Engineer"},
            "packet_fingerprint": {"packet_hash": "packet-1"},
        },
        "approved_fields": {"full_name": "Ada Lovelace", "email": "ada@example.invalid"},
        "screenshot_dir": str(tmp_path),
    }
    values.update(overrides)
    return BrowserRunRequest(**values)


@pytest.mark.asyncio
async def test_visible_run_fills_only_allowlisted_fields_and_audits(tmp_path: Path) -> None:
    page = FakePage()
    result = await AssistedApplicationWorker(page, GreenhouseLikeAdapter()).run(request(tmp_path))

    assert result.status == "stopped_before_submit"
    assert page.goto_urls == ["https://jobs.invalid/apply/1"]
    assert page.fills == [
        ("input[name='name']", "Ada Lovelace"),
        ("input[name='email']", "ada@example.invalid"),
    ]
    assert len(result.screenshots) == 2
    assert {event["type"] for event in result.events} >= {
        "run_started",
        "field_filled",
        "screenshot_captured",
        "stopped_before_submit",
    }
    assert all(Path(item["path"]).exists() for item in result.screenshots)


@pytest.mark.asyncio
async def test_rejects_sensitive_unknown_and_headless_requests(tmp_path: Path) -> None:
    page = FakePage()
    worker = AssistedApplicationWorker(page, GreenhouseLikeAdapter())

    for fields in ({"password": "secret"}, {"resume_upload": "file"}):
        with pytest.raises(BrowserRunRejected):
            await worker.run(request(tmp_path, approved_fields=fields))
    with pytest.raises(BrowserRunRejected, match="headless"):
        await worker.run(request(tmp_path, headless=True))
    with pytest.raises(BrowserRunRejected, match="fingerprint"):
        await worker.run(request(tmp_path, expected_packet_fingerprint={"packet_hash": "other"}))


@pytest.mark.asyncio
async def test_page_without_submit_method_proves_submit_is_unreachable(tmp_path: Path) -> None:
    page = FakePage()
    result = await AssistedApplicationWorker(page, GreenhouseLikeAdapter()).run(request(tmp_path))
    assert result.steps[-1]["action"] == "stopped_before_submit"
    assert not hasattr(page, "submit")
