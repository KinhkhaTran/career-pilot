"""Fixture test suite: the Workday adapter + runner proven against the mock.

Requirement 17: the adapter must pass this suite before any real employer site
is touched. Every case runs entirely in memory against MockWorkdayApplication.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.browser_worker import (
    ApprovalBinding,
    FieldCategory,
    FieldValue,
    InMemorySubmissionGuard,
    InMemoryTokenStore,
    PauseReason,
    RunContext,
    RunnerConfig,
    SupervisedApplicationRunner,
    WorkdayAdapter,
    issue_token,
)
from app.browser_worker.runner import BrowserRunRejected
from tests.fixtures.mock_workday import MockWorkdayApplication

SECRET = "runner-secret"
FINGERPRINT = {"packet_hash": "packet-1", "profile_version": 1}


def full_answer_set() -> dict[FieldCategory, FieldValue]:
    text = {
        FieldCategory.FIRST_NAME: "Ada",
        FieldCategory.LAST_NAME: "Lovelace",
        FieldCategory.EMAIL: "ada@example.invalid",
        FieldCategory.PHONE: "+1-555-0100",
        FieldCategory.ADDRESS_LINE1: "1 Analytical Engine Way",
        FieldCategory.CITY: "London",
        FieldCategory.STATE: "CA",
        FieldCategory.POSTAL_CODE: "94000",
        FieldCategory.COUNTRY: "US",
        FieldCategory.EMPLOYMENT_HISTORY: "Lead Engineer, Acme",
        FieldCategory.EDUCATION: "BSc Mathematics",
        FieldCategory.SKILLS: "Python, Rust",
        FieldCategory.LINKEDIN_URL: "https://linkedin.example.invalid/ada",
        FieldCategory.WORK_AUTHORIZATION: "authorized",
        FieldCategory.SPONSORSHIP: "no",
        FieldCategory.RELOCATION: "yes",
        FieldCategory.START_DATE: "2026-09-01",
        FieldCategory.SCREENING_ANSWER: "8",
        FieldCategory.RESUME: "resume.pdf",
    }
    return {cat: FieldValue(value=val, confidence=0.96) for cat, val in text.items()}


def make_ctx(tmp_path: Path, **overrides: object) -> RunContext:
    resume = tmp_path / "resume.pdf"
    resume.write_text("résumé")
    values: dict[str, object] = {
        "application_id": "app-1",
        "job_id": "job-1",
        "run_id": "run-1",
        "application_url": "https://acme.wd1.myworkdayjobs.com/apply/1",
        "resume_version": 3,
        "answer_set_version": 2,
        "packet_fingerprint": FINGERPRINT,
        "expected_packet_fingerprint": FINGERPRINT,
        "immutable_inputs": {
            "profile_version": 1,
            "job_snapshot_hash": "job-hash",
            "job_snapshot": {"title": "Engineer"},
            "packet_fingerprint": FINGERPRINT,
        },
        "answer_set": full_answer_set(),
        "resume_path": str(resume),
        "screenshot_dir": str(tmp_path / "shots"),
    }
    values.update(overrides)
    return RunContext(**values)  # type: ignore[arg-type]


def make_runner(
    sim: MockWorkdayApplication,
    *,
    mode: str = "allow_submit",
    token_store: InMemoryTokenStore | None = None,
    guard: InMemorySubmissionGuard | None = None,
) -> SupervisedApplicationRunner:
    return SupervisedApplicationRunner(
        sim,
        WorkdayAdapter(),
        config=RunnerConfig(confidence_threshold=0.8, submission_mode=mode, approval_secret=SECRET),
        token_store=token_store or InMemoryTokenStore(),
        submission_guard=guard or InMemorySubmissionGuard(),
    )


# --- fills + pause on sensitive step ---------------------------------------


async def test_fills_early_steps_then_pauses_at_voluntary_disclosures(tmp_path: Path) -> None:
    sim = MockWorkdayApplication()
    result = await make_runner(sim).run(make_ctx(tmp_path))

    assert result.status == "paused"
    assert result.pause is not None and result.pause.reason is PauseReason.LEGALLY_SENSITIVE
    # Steps 1-3 were filled from the approved answer set.
    filled = {m["category"] for m in result.field_mappings}
    assert {"first_name", "email", "work_authorization", "sponsorship", "resume"} <= filled
    # Never filled a sensitive field.
    assert "eeo_gender" not in filled and "attestation" not in filled
    # Audit: a screenshot + browser-state per visited step.
    assert len(result.screenshots) >= 3
    assert all(Path(s["path"]).exists() for s in result.screenshots)
    assert result.browser_states and result.browser_states[0]["step"] == "my_information"


async def test_missing_answer_pauses(tmp_path: Path) -> None:
    answers = full_answer_set()
    del answers[FieldCategory.EMAIL]
    sim = MockWorkdayApplication()
    result = await make_runner(sim).run(make_ctx(tmp_path, answer_set=answers))
    assert result.status == "paused"
    assert result.pause is not None
    assert result.pause.reason is PauseReason.MISSING_ANSWER
    assert result.pause.field == "email"


async def test_low_confidence_pauses(tmp_path: Path) -> None:
    answers = full_answer_set()
    answers[FieldCategory.PHONE] = FieldValue(value="+1-555-0100", confidence=0.4)
    sim = MockWorkdayApplication()
    result = await make_runner(sim).run(make_ctx(tmp_path, answer_set=answers))
    assert result.status == "paused"
    assert result.pause is not None and result.pause.reason is PauseReason.LOW_CONFIDENCE


async def test_captcha_interrupt_pauses_and_is_never_solved(tmp_path: Path) -> None:
    sim = MockWorkdayApplication(interrupt_at={"my_information": "captcha"})
    result = await make_runner(sim).run(make_ctx(tmp_path))
    assert result.status == "paused"
    assert result.pause is not None and result.pause.reason is PauseReason.CAPTCHA
    # Nothing was filled — the runner stopped before touching the form.
    assert result.field_mappings == []


async def test_validation_error_pauses_with_details(tmp_path: Path) -> None:
    sim = MockWorkdayApplication(reject_fields=frozenset({"phone-number"}))
    result = await make_runner(sim).run(make_ctx(tmp_path))
    assert result.status == "paused"
    assert result.pause is not None and result.pause.reason is PauseReason.VALIDATION_ERROR
    assert result.errors and "correct" in result.errors[0].lower()


async def test_headless_and_fingerprint_mismatch_are_rejected(tmp_path: Path) -> None:
    sim = MockWorkdayApplication()
    with pytest.raises(BrowserRunRejected, match="visible"):
        await make_runner(sim).run(make_ctx(tmp_path, headless=True))
    with pytest.raises(BrowserRunRejected, match="fingerprint"):
        await make_runner(sim).run(
            make_ctx(tmp_path, expected_packet_fingerprint={"packet_hash": "other"})
        )


# --- review, token-gated submit, idempotency --------------------------------


async def test_resume_stops_at_review_without_token(tmp_path: Path) -> None:
    sim = MockWorkdayApplication()
    runner = make_runner(sim)
    # First pass fills 1-3 and pauses at disclosures.
    await runner.run(make_ctx(tmp_path))
    # Human completes disclosures + attestation and advances to Review.
    sim.human_complete_voluntary_disclosures()
    # Resume, but no approval token supplied.
    result = await runner.run(make_ctx(tmp_path, approval_token=None))
    assert result.status == "stopped_at_review"
    assert result.final_page_fingerprint is not None
    assert any(e["type"] == "state_reported_to_dashboard" for e in result.events)


async def test_token_gated_single_submit_then_idempotent(tmp_path: Path) -> None:
    sim = MockWorkdayApplication()
    token_store = InMemoryTokenStore()
    guard = InMemorySubmissionGuard()
    runner = make_runner(sim, token_store=token_store, guard=guard)

    await runner.run(make_ctx(tmp_path))
    sim.human_complete_voluntary_disclosures()

    # Discover the review-page fingerprint (as the dashboard would).
    staged = await runner.run(make_ctx(tmp_path, approval_token=None))
    fingerprint = staged.final_page_fingerprint
    assert fingerprint is not None

    binding = ApprovalBinding(
        application_id="app-1",
        job_id="job-1",
        resume_version=3,
        answer_set_version=2,
        browser_run_id="run-1",
        final_page_fingerprint=fingerprint,
    )
    token = issue_token("tok-1", binding, secret=SECRET)

    result = await runner.run(make_ctx(tmp_path, approval_token=token))
    assert result.status == "submitted"
    assert result.submitted is True
    assert result.confirmation is not None
    assert result.confirmation["confirmation_number"] == "WD-CONF-2026-0001"
    assert sim.submitted is True

    # Idempotent replay: a resumed run does not submit a second time.
    replay = await runner.run(make_ctx(tmp_path, approval_token=token))
    assert replay.status == "submitted"
    assert replay.submitted is True

    # The one-time token is spent and cannot authorise another submission.
    from app.browser_worker import ApprovalError, verify_and_consume

    with pytest.raises(ApprovalError, match="already been used"):
        await verify_and_consume(token, binding, secret=SECRET, store=token_store)


async def test_wrong_token_stops_at_review_without_submitting(tmp_path: Path) -> None:
    sim = MockWorkdayApplication()
    runner = make_runner(sim)
    await runner.run(make_ctx(tmp_path))
    sim.human_complete_voluntary_disclosures()

    bad_binding = ApprovalBinding(
        application_id="app-1",
        job_id="job-1",
        resume_version=999,  # wrong résumé version
        answer_set_version=2,
        browser_run_id="run-1",
        final_page_fingerprint="whatever",
    )
    bad_token = issue_token("tok-x", bad_binding, secret=SECRET)
    result = await runner.run(make_ctx(tmp_path, approval_token=bad_token))
    assert result.status == "stopped_at_review"
    assert sim.submitted is False


async def test_stop_before_submit_mode_never_submits_even_with_token(tmp_path: Path) -> None:
    sim = MockWorkdayApplication()
    runner = make_runner(sim, mode="stop_before_submit")
    await runner.run(make_ctx(tmp_path))
    sim.human_complete_voluntary_disclosures()

    staged = await runner.run(make_ctx(tmp_path, approval_token=None))
    binding = ApprovalBinding(
        application_id="app-1",
        job_id="job-1",
        resume_version=3,
        answer_set_version=2,
        browser_run_id="run-1",
        final_page_fingerprint=staged.final_page_fingerprint or "",
    )
    token = issue_token("tok-1", binding, secret=SECRET)
    result = await runner.run(make_ctx(tmp_path, approval_token=token))
    assert result.status == "stopped_at_review"
    assert sim.submitted is False
