"""Supervised, approval-bound Workday application runner.

Design invariants:

* Runs only against a **visible** (headful) page; headless is rejected.
* Fills only human-approved, non-sensitive fields; pauses on anything missing,
  low-confidence, legally sensitive, or requiring an attestation.
* Never solves CAPTCHA/MFA/identity — it detects them and hands off to a human.
* Stops at the employer's Review page and reports state for dashboard review.
* Clicks the existing Submit control **exactly once**, and only when a valid,
  single-use approval token authorises this exact application state.
* Resumable and idempotent: a confirmed application is never submitted twice.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .approval import ApprovalBinding, ApprovalError, TokenStore, verify_and_consume
from .fields import (
    CHECKBOX_KIND,
    FILE_KIND,
    RADIO_KIND,
    SELECT_KIND,
    DetectedField,
    FieldCategory,
    FieldValue,
    redact,
)
from .page import BrowserPage
from .pause import HUMAN_HANDOFF_REASONS, PauseReason, PauseSignal, RunPaused
from .workday import WorkdayAdapter, WorkdayStep

MAX_STEPS = 12


class BrowserRunRejected(ValueError):
    """Binding/allowlist failure — the run must not even start."""


class SubmissionGuard(Protocol):
    """Cross-run idempotency: has this application already been submitted?"""

    async def is_submitted(self, application_id: str) -> bool: ...
    async def mark_submitted(self, application_id: str, evidence: dict[str, str]) -> None: ...


class InMemorySubmissionGuard:
    def __init__(self) -> None:
        self._submitted: dict[str, dict[str, str]] = {}

    async def is_submitted(self, application_id: str) -> bool:
        return application_id in self._submitted

    async def mark_submitted(self, application_id: str, evidence: dict[str, str]) -> None:
        self._submitted.setdefault(application_id, evidence)


@dataclass(frozen=True)
class RunContext:
    application_id: str
    job_id: str
    run_id: str
    application_url: str
    resume_version: int
    answer_set_version: int
    packet_fingerprint: dict[str, Any]
    expected_packet_fingerprint: dict[str, Any]
    immutable_inputs: dict[str, Any]
    answer_set: dict[FieldCategory, FieldValue]
    resume_path: str | None = None
    cover_letter_path: str | None = None
    approval_token: str | None = None
    headless: bool = False
    screenshot_dir: str = "artifacts/browser-runs"


@dataclass
class RunnerConfig:
    confidence_threshold: float = 0.8
    submission_mode: str = "stop_before_submit"
    approval_secret: str = ""


@dataclass
class SupervisedRunResult:
    status: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    screenshots: list[dict[str, str]] = field(default_factory=list)
    field_mappings: list[dict[str, Any]] = field(default_factory=list)
    entered_values: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    browser_states: list[dict[str, Any]] = field(default_factory=list)
    pause: PauseSignal | None = None
    final_page_fingerprint: str | None = None
    confirmation: dict[str, str] | None = None
    submitted: bool = False


class SupervisedApplicationRunner:
    def __init__(
        self,
        page: BrowserPage,
        adapter: WorkdayAdapter,
        *,
        config: RunnerConfig,
        token_store: TokenStore,
        submission_guard: SubmissionGuard,
    ) -> None:
        self.page = page
        self.adapter = adapter
        self.config = config
        self.token_store = token_store
        self.guard = submission_guard

    async def run(self, ctx: RunContext) -> SupervisedRunResult:
        self._validate_binding(ctx)
        result = SupervisedRunResult(status="running")
        result.events.append(
            {"type": "run_started", "adapter": self.adapter.name, "run_id": ctx.run_id}
        )
        try:
            await self._navigate_to_form(ctx, result)
            await self._step_loop(ctx, result)
        except RunPaused as paused:
            self._record_pause(result, paused.signal)
        return result

    # -- binding & allowlist -------------------------------------------------

    def _validate_binding(self, ctx: RunContext) -> None:
        if ctx.headless:
            raise BrowserRunRejected(
                "headless browser runs are forbidden; assisted runs must be visible"
            )
        if ctx.packet_fingerprint != ctx.expected_packet_fingerprint:
            raise BrowserRunRejected("packet fingerprint mismatch; re-approval is required")
        required = {"profile_version", "job_snapshot_hash", "job_snapshot", "packet_fingerprint"}
        if not required.issubset(ctx.immutable_inputs):
            raise BrowserRunRejected("immutable application inputs are incomplete")
        if not ctx.application_id or not ctx.application_url:
            raise BrowserRunRejected("application binding is required")
        # The answer set may only carry lawful, fillable categories.
        from .fields import FILLABLE_CATEGORIES

        illegal = set(ctx.answer_set) - FILLABLE_CATEGORIES
        if illegal:
            raise BrowserRunRejected(
                f"answer set contains non-fillable categories: {sorted(c.value for c in illegal)}"
            )

    # -- navigation ----------------------------------------------------------

    async def _navigate_to_form(self, ctx: RunContext, result: SupervisedRunResult) -> None:
        # Only navigate if we are not already on a recognised form. On resume the
        # human may have advanced the page past login/interstitials manually.
        if not await self.adapter.at_application_form(self.page):
            await self.page.goto(ctx.application_url)
            result.steps.append({"action": "goto", "url": ctx.application_url})
        for signal in await self.adapter.detect_interrupts(self.page):
            raise RunPaused(signal)
        if not await self.adapter.at_application_form(self.page):
            raise RunPaused(
                PauseSignal(
                    PauseReason.NOT_AT_APPLICATION_FORM,
                    "no recognised application form is present; a human must complete "
                    "login/navigation in the visible browser",
                )
            )

    # -- main loop -----------------------------------------------------------

    async def _step_loop(self, ctx: RunContext, result: SupervisedRunResult) -> None:
        for _ in range(MAX_STEPS):
            for signal in await self.adapter.detect_interrupts(self.page):
                raise RunPaused(signal)

            step = await self.adapter.current_step(self.page)
            await self._snapshot(ctx, result, step)

            if step is WorkdayStep.CONFIRMATION:
                await self._record_confirmation(ctx, result)
                return
            if step is WorkdayStep.REVIEW:
                await self._handle_review(ctx, result)
                return

            fields = await self.adapter.fields_for_step(self.page, step)
            await self._fill_step(ctx, result, step, fields)
            await self._advance_with_validation(ctx, result, step)
        result.status = "failed"
        result.errors.append("exceeded maximum step count without reaching Review")

    async def _fill_step(
        self,
        ctx: RunContext,
        result: SupervisedRunResult,
        step: WorkdayStep,
        fields: list[DetectedField],
    ) -> None:
        for detected in fields:
            if detected.is_sensitive:
                reason = (
                    PauseReason.ATTESTATION
                    if detected.category is FieldCategory.ATTESTATION
                    else PauseReason.LEGALLY_SENSITIVE
                )
                raise RunPaused(
                    PauseSignal(
                        reason,
                        f"'{detected.label}' must be answered by a human; the runner "
                        "never fills legally sensitive fields or attestations",
                        field=detected.category.value,
                    )
                )
            answer = ctx.answer_set.get(detected.category)
            if answer is None:
                if not detected.required:
                    continue
                raise RunPaused(
                    PauseSignal(
                        PauseReason.MISSING_ANSWER,
                        f"no approved answer for required field '{detected.label}'",
                        field=detected.category.value,
                    )
                )
            if answer.confidence < self.config.confidence_threshold:
                raise RunPaused(
                    PauseSignal(
                        PauseReason.LOW_CONFIDENCE,
                        f"answer for '{detected.label}' has confidence "
                        f"{answer.confidence:.2f} < threshold "
                        f"{self.config.confidence_threshold:.2f}",
                        field=detected.category.value,
                        detail={"confidence": answer.confidence},
                    )
                )
            await self._write_field(ctx, detected, answer)
            result.field_mappings.append(
                {
                    "step": step.value,
                    "category": detected.category.value,
                    "selector": detected.selector,
                    "kind": detected.kind,
                    "label": detected.label,
                }
            )
            result.entered_values.append(
                {
                    "category": detected.category.value,
                    "value": redact(detected.category, answer.value),
                    "confidence": answer.confidence,
                }
            )
            result.events.append({"type": "field_filled", "field": detected.category.value})

    async def _write_field(
        self, ctx: RunContext, detected: DetectedField, answer: FieldValue
    ) -> None:
        if detected.kind == FILE_KIND:
            path = (
                ctx.resume_path
                if detected.category is FieldCategory.RESUME
                else ctx.cover_letter_path
            )
            if not path:
                raise RunPaused(
                    PauseSignal(
                        PauseReason.MISSING_ANSWER,
                        f"no approved file to upload for '{detected.label}'",
                        field=detected.category.value,
                    )
                )
            await self.page.set_input_files(detected.selector, path)
        elif detected.kind == SELECT_KIND:
            await self.page.select_option(detected.selector, answer.value)
        elif detected.kind == RADIO_KIND:
            await self.page.check(f"{detected.selector}[value='{answer.value}']")
        elif detected.kind == CHECKBOX_KIND:  # pragma: no cover - sensitive, never reached
            await self.page.check(detected.selector)
        else:
            await self.page.fill(detected.selector, answer.value)

    async def _advance_with_validation(
        self, ctx: RunContext, result: SupervisedRunResult, step: WorkdayStep
    ) -> None:
        await self.adapter.advance(self.page)
        result.steps.append({"action": "advance", "from_step": step.value})
        # If we did not progress, the server rejected input. Re-read + surface it.
        if await self.adapter.current_step(self.page) is step:
            errors = await self.adapter.read_validation_errors(self.page)
            result.errors.extend(errors)
            raise RunPaused(
                PauseSignal(
                    PauseReason.VALIDATION_ERROR,
                    "the form reported validation errors that need human attention",
                    detail={"errors": errors},
                )
            )

    # -- review & submit -----------------------------------------------------

    async def _handle_review(self, ctx: RunContext, result: SupervisedRunResult) -> None:
        summary = await self.adapter.review_summary(self.page)
        fingerprint = hashlib.sha256(summary.encode()).hexdigest()
        result.final_page_fingerprint = fingerprint
        result.events.append({"type": "reached_review", "final_page_fingerprint": fingerprint})

        # Idempotency: never re-drive a submission that already completed.
        if await self.guard.is_submitted(ctx.application_id):
            result.status = "submitted"
            result.submitted = True
            result.events.append({"type": "already_submitted", "source": "submission_guard"})
            return

        interrupts = await self.adapter.detect_interrupts(self.page)
        if interrupts:
            raise RunPaused(interrupts[0])

        binding = ApprovalBinding(
            application_id=ctx.application_id,
            job_id=ctx.job_id,
            resume_version=ctx.resume_version,
            answer_set_version=ctx.answer_set_version,
            browser_run_id=ctx.run_id,
            final_page_fingerprint=fingerprint,
        )

        if self.config.submission_mode != "allow_submit" or not ctx.approval_token:
            self._stop_at_review(result, "no valid approval token; submission mode is "
                                 f"{self.config.submission_mode!r}")
            return
        try:
            token_id = await verify_and_consume(
                ctx.approval_token,
                binding,
                secret=self.config.approval_secret,
                store=self.token_store,
            )
        except ApprovalError as exc:
            result.errors.append(str(exc))
            self._stop_at_review(result, f"approval rejected: {exc}")
            return

        await self._submit_once(ctx, result, token_id)

    def _stop_at_review(self, result: SupervisedRunResult, reason: str) -> None:
        signal = PauseSignal(PauseReason.STOPPED_AT_REVIEW, reason)
        result.status = "stopped_at_review"
        result.pause = signal
        result.events.append(signal.as_event())
        result.events.append({"type": "state_reported_to_dashboard"})

    async def _submit_once(
        self, ctx: RunContext, result: SupervisedRunResult, token_id: str
    ) -> None:
        result.events.append({"type": "approval_verified", "token_id": token_id})
        await self.page.click(self.adapter.submit_selector())
        result.steps.append({"action": "submit_clicked", "token_id": token_id})
        result.events.append({"type": "submit_clicked", "token_id": token_id})
        await self._snapshot(ctx, result, await self.adapter.current_step(self.page))

        if await self.adapter.is_confirmation_page(self.page):
            await self._record_confirmation(ctx, result)
            return
        errors = await self.adapter.read_validation_errors(self.page)
        result.errors.extend(errors)
        result.status = "failed"
        result.events.append({"type": "submit_did_not_confirm", "errors": errors})

    async def _record_confirmation(self, ctx: RunContext, result: SupervisedRunResult) -> None:
        evidence = await self.adapter.confirmation_evidence(self.page)
        await self.guard.mark_submitted(ctx.application_id, evidence)
        result.status = "submitted"
        result.submitted = True
        result.confirmation = evidence
        result.events.append({"type": "submission_confirmed", **evidence})

    # -- audit ---------------------------------------------------------------

    async def _snapshot(
        self, ctx: RunContext, result: SupervisedRunResult, step: WorkdayStep
    ) -> None:
        label = step.value
        url = await self.page.current_url()
        state = {"step": label, "url": url}
        result.browser_states.append(state)
        result.events.append({"type": "browser_state", **state})
        digest = hashlib.sha256(
            f"{ctx.run_id}:{label}:{len(result.screenshots)}".encode()
        ).hexdigest()[:16]
        path = Path(ctx.screenshot_dir) / f"{ctx.run_id}-{label}-{digest}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=str(path))
        result.screenshots.append({"label": label, "path": str(path)})
        result.events.append({"type": "screenshot_captured", "label": label, "path": str(path)})

    def _record_pause(self, result: SupervisedRunResult, signal: PauseSignal) -> None:
        result.pause = signal
        result.events.append(signal.as_event())
        if signal.reason in HUMAN_HANDOFF_REASONS:
            result.status = (
                "stopped_at_review"
                if signal.reason is PauseReason.STOPPED_AT_REVIEW
                else "paused"
            )
        else:
            result.status = "paused"
