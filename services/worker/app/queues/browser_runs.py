"""ARQ entrypoint for an approval-bound assisted browser run."""
from __future__ import annotations

from typing import Any

from app.browser_worker import AssistedApplicationWorker, GenericMockATSAdapter
from app.browser_worker.worker import BrowserRunRequest


async def assisted_application_task(
    ctx: dict[str, Any],
    *,
    application_id: str,
    run_id: str,
    application_url: str,
    packet_fingerprint: dict[str, Any],
    expected_packet_fingerprint: dict[str, Any],
    immutable_inputs: dict[str, Any],
    approved_fields: dict[str, str],
) -> dict[str, Any]:
    """Execute only with a caller-provided Playwright-compatible page.

    Production wiring supplies a visible/headful page. The task deliberately has
    no browser launcher or network credentials, so unattended employer-site
    automation cannot be enabled by accident.
    """
    page = ctx.get("browser_page")
    if page is None:
        raise RuntimeError("browser_page is required; live browser launching is disabled")
    result = await AssistedApplicationWorker(page, GenericMockATSAdapter()).run(
        BrowserRunRequest(
            application_id=application_id,
            application_url=application_url,
            packet_fingerprint=packet_fingerprint,
            expected_packet_fingerprint=expected_packet_fingerprint,
            immutable_inputs=immutable_inputs,
            approved_fields=approved_fields,
            headless=False,
        )
    )
    from app.db import get_connection, persist_browser_run_result

    async with get_connection() as conn:
        await persist_browser_run_result(
            conn,
            run_id,
            status=result.status,
            stopped_before_submit=result.status == "stopped_before_submit",
            steps=result.steps,
            events=result.events,
            screenshots=result.screenshots,
        )
    return {"status": result.status, "steps": result.steps, "events": result.events, "screenshots": result.screenshots}
