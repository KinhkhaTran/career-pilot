"""ARQ entrypoint for a supervised, token-gated Workday application run.

This is the production seam that drives :class:`SupervisedApplicationRunner`
against a real, visible browser. It is exercised end-to-end only with an
operator-supervised page; the deterministic behaviour it relies on is proven by
the in-memory fixture suite (``tests/test_supervised_runner.py``).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.browser_worker import (
    FieldCategory,
    FieldValue,
    RunContext,
    RunnerConfig,
    SupervisedApplicationRunner,
    WorkdayAdapter,
)
from app.browser_worker.launcher import launch_persistent_headful
from app.browser_worker.page import BrowserPage
from app.config import worker_settings


def _deserialize_answer_set(raw: dict[str, dict[str, Any]]) -> dict[FieldCategory, FieldValue]:
    """Convert wire-format answers into a typed, category-keyed answer set."""
    answers: dict[FieldCategory, FieldValue] = {}
    for key, payload in raw.items():
        category = FieldCategory(key)
        answers[category] = FieldValue(
            value=str(payload["value"]),
            confidence=float(payload.get("confidence", 0.0)),
            source=str(payload.get("source", "approved_answer_set")),
        )
    return answers


@asynccontextmanager
async def _resolve_page(ctx: dict[str, Any]) -> AsyncIterator[BrowserPage]:
    """Prefer an operator-provided page; otherwise open a persistent headful one."""
    injected = ctx.get("browser_page")
    if injected is not None:
        yield injected
        return
    async with launch_persistent_headful(worker_settings.browser_profile_dir) as page:
        yield page


async def supervised_application_task(
    ctx: dict[str, Any],
    *,
    application_id: str,
    job_id: str,
    run_id: str,
    application_url: str,
    packet_fingerprint: dict[str, Any],
    expected_packet_fingerprint: dict[str, Any],
    immutable_inputs: dict[str, Any],
    answer_set: dict[str, dict[str, Any]],
    resume_path: str | None = None,
    cover_letter_path: str | None = None,
    approval_token: str | None = None,
) -> dict[str, Any]:
    from app.db import (
        DbSubmissionGuard,
        DbTokenStore,
        get_connection,
        get_token_binding_values,
        persist_supervised_run_result,
    )

    resume_version = int(packet_fingerprint.get("resume_version", 0))
    answer_set_version = 0
    async with get_connection() as conn:
        # If a token is presented, bind exactly to the values the API signed.
        if approval_token:
            token_id = approval_token.split(".", 1)[0]
            values = await get_token_binding_values(conn, token_id)
            if values is not None:
                resume_version = values.resume_version
                answer_set_version = values.answer_set_version

        runner = SupervisedApplicationRunner(
            # placeholder page swapped in below
            page=None,  # type: ignore[arg-type]
            adapter=WorkdayAdapter(),
            config=RunnerConfig(
                confidence_threshold=worker_settings.fill_confidence_threshold,
                submission_mode=worker_settings.initial_submission_mode,
                approval_secret=worker_settings.approval_signing_secret,
            ),
            token_store=DbTokenStore(conn),
            submission_guard=DbSubmissionGuard(conn),
        )
        run_ctx = RunContext(
            application_id=application_id,
            job_id=job_id,
            run_id=run_id,
            application_url=application_url,
            resume_version=resume_version,
            answer_set_version=answer_set_version,
            packet_fingerprint=packet_fingerprint,
            expected_packet_fingerprint=expected_packet_fingerprint,
            immutable_inputs=immutable_inputs,
            answer_set=_deserialize_answer_set(answer_set),
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            approval_token=approval_token,
        )
        async with _resolve_page(ctx) as page:
            runner.page = page
            result = await runner.run(run_ctx)

        await persist_supervised_run_result(
            conn,
            run_id,
            status=result.status,
            submitted=result.submitted,
            final_page_fingerprint=result.final_page_fingerprint,
            confirmation=result.confirmation,
            steps=result.steps,
            events=result.events,
            screenshots=result.screenshots,
        )

    return {
        "status": result.status,
        "submitted": result.submitted,
        "final_page_fingerprint": result.final_page_fingerprint,
        "confirmation": result.confirmation,
        "pause": result.pause.as_event() if result.pause else None,
    }
