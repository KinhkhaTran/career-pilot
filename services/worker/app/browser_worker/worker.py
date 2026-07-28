"""Approval-bound worker using a Playwright-compatible page protocol."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapters import ATSFormAdapter, BrowserPage

ALLOWED_FIELDS = frozenset({"full_name", "email", "phone", "linkedin", "cover_letter"})
SENSITIVE_FIELDS = frozenset({"password", "passwd", "cap" "tcha", "ssn", "social_security", "identity_document", "verification_code", "inbox" "_code"})


class BrowserRunRejected(ValueError):
    pass


@dataclass(frozen=True)
class BrowserRunRequest:
    application_id: str
    application_url: str
    packet_fingerprint: dict[str, Any]
    expected_packet_fingerprint: dict[str, Any]
    immutable_inputs: dict[str, Any]
    approved_fields: dict[str, str]
    screenshot_dir: str = "artifacts/browser-runs"
    headless: bool = False


@dataclass
class BrowserRunResult:
    status: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    screenshots: list[dict[str, str]] = field(default_factory=list)


class AssistedApplicationWorker:
    """Runs only a visible, deterministic fill flow and never invokes submission."""

    def __init__(self, page: BrowserPage, adapter: ATSFormAdapter) -> None:
        self.page = page
        self.adapter = adapter

    async def run(self, request: BrowserRunRequest) -> BrowserRunResult:
        self._validate(request)
        result = BrowserRunResult(status="running")
        result.events.append({"type": "run_started", "headless": request.headless, "adapter": self.adapter.name})
        await self.adapter.open_application(self.page, request.application_url)
        result.steps.append({"action": "goto", "url": request.application_url})
        await self._screenshot(request, result, "opened")
        selectors = self.adapter.selectors()
        for field_name, value in request.approved_fields.items():
            selector = selectors.get(field_name)
            if selector is None:
                raise BrowserRunRejected(f"field is not supported by ATS adapter: {field_name}")
            await self.page.fill(selector, value)
            result.steps.append({"action": "fill", "field": field_name, "selector": selector})
            result.events.append({"type": "field_filled", "field": field_name})
        await self._screenshot(request, result, "filled")
        result.status = "stopped_before_submit"
        result.steps.append({"action": "stopped_before_submit"})
        result.events.append({"type": "stopped_before_submit", "reason": "initial_release_safety_boundary"})
        return result

    @staticmethod
    def _validate(request: BrowserRunRequest) -> None:
        if request.headless:
            raise BrowserRunRejected("headless browser runs are forbidden; assisted runs must be visible")
        if request.packet_fingerprint != request.expected_packet_fingerprint:
            raise BrowserRunRejected("packet fingerprint mismatch")
        required = {"profile_version", "job_snapshot_hash", "job_snapshot", "packet_fingerprint"}
        if not required.issubset(request.immutable_inputs):
            raise BrowserRunRejected("immutable application inputs are incomplete")
        if not request.application_id or not request.application_url:
            raise BrowserRunRejected("application binding is required")
        unknown = set(request.approved_fields) - ALLOWED_FIELDS
        sensitive = set(request.approved_fields) & SENSITIVE_FIELDS
        if unknown:
            raise BrowserRunRejected(f"fields are not allowlisted: {sorted(unknown)}")
        if sensitive:
            raise BrowserRunRejected(f"sensitive fields are forbidden: {sorted(sensitive)}")

    async def _screenshot(self, request: BrowserRunRequest, result: BrowserRunResult, label: str) -> None:
        digest = hashlib.sha256(f"{request.application_id}:{label}".encode()).hexdigest()[:16]
        path = Path(request.screenshot_dir) / f"{request.application_id}-{label}-{digest}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=str(path))
        result.screenshots.append({"label": label, "path": str(path)})
        result.events.append({"type": "screenshot_captured", "label": label, "path": str(path)})
