"""
Approval-bound assisted application runs.

An assisted run is created only for an `approved` application whose packet
fingerprint and immutable inputs match exactly. The run then advances one step at
a time against the in-process mock ATS sandbox, so a human can watch it, pause
it, and resume it from real persisted state.

SAFETY BOUNDARY
---------------
* Targets are validated by `assert_mock_target`; only `mock-ats://` sandbox URLs
  are accepted. Employer URLs are returned for manual reading, never driven.
* The plan has no submit action. Every run terminates at
  `stopped_before_submit`, which is also where the application lands.
* Recording a sandbox receipt does not move the application to `submitted` —
  that state stays unreachable under `INITIAL_SUBMISSION_MODE=stop_before_submit`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal, cast

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.approval import ApprovalBinding, issue_token
from app.assisted import (
    MOCK_ATS_LABEL,
    PAUSED,
    RUNNING,
    STOPPED_BEFORE_SUBMIT,
    MockAtsError,
    RunnerError,
    assert_advanceable,
    assert_mock_target,
    assert_pausable,
    assert_resumable,
    build_plan,
    execute_step,
    mock_ats_url,
    next_status,
    record_submission,
)
from app.config import settings
from app.database import get_db
from app.models.application import Application, ApplicationEvent
from app.models.browser_run import ApprovalToken, BrowserRun, BrowserRunEvent, BrowserRunStep
from app.models.job import Job
from app.models.material import ApplicationMaterial
from app.models.mock_ats import MockAtsSubmission
from app.models.profile import CandidateProfile
from app.schemas.browser_run import (
    BrowserRunAdvanceRequest,
    BrowserRunLaunchContextSchema,
    BrowserRunSchema,
    BrowserRunStartRequest,
)
from app.schemas.mock_ats import MockAtsReceiptSchema
from app.state_machine.application import ApplicationStatus, StateMachineError, transition

router = APIRouter()


class ApprovalTokenRequest(BaseModel):
    final_page_fingerprint: str
    resume_version: int
    confirm: Literal[True]


def _load_options() -> tuple[Any, ...]:
    return (
        selectinload(BrowserRun.steps),
        selectinload(BrowserRun.events),
        selectinload(BrowserRun.screenshots),
    )


async def _reload(db: AsyncSession, run_id: str) -> BrowserRun:
    result = await db.execute(
        select(BrowserRun).where(BrowserRun.id == run_id).options(*_load_options())
    )
    return result.scalar_one()


async def _get_run(db: AsyncSession, app_id: str, run_id: str) -> BrowserRun:
    result = await db.execute(
        select(BrowserRun)
        .where(BrowserRun.id == run_id, BrowserRun.application_id == app_id)
        .options(*_load_options())
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Browser run not found")
    return run


async def _next_sequences(db: AsyncSession, run_id: str) -> tuple[int, int]:
    step_max = await db.scalar(
        select(func.max(BrowserRunStep.sequence)).where(BrowserRunStep.run_id == run_id)
    )
    event_max = await db.scalar(
        select(func.max(BrowserRunEvent.sequence)).where(BrowserRunEvent.run_id == run_id)
    )
    return (step_max or -1) + 1, (event_max or -1) + 1


async def _append_event(
    db: AsyncSession, run_id: str, event_type: str, detail: dict[str, Any]
) -> None:
    _, event_seq = await _next_sequences(db, run_id)
    db.add(
        BrowserRunEvent(
            id=str(uuid.uuid4()),
            run_id=run_id,
            sequence=event_seq,
            event_type=event_type,
            detail=detail,
        )
    )


def _expected_inputs(app: Application) -> dict[str, Any]:
    return {
        "profile_version": app.profile_version,
        "job_snapshot_hash": app.job_snapshot_hash,
        "job_snapshot": app.job_snapshot,
        "packet_fingerprint": app.packet_fingerprint,
    }


@router.get("/{app_id}/browser-runs/launch-context", response_model=BrowserRunLaunchContextSchema)
async def get_launch_context(
    app_id: str, db: AsyncSession = Depends(get_db)
) -> BrowserRunLaunchContextSchema:
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.APPROVED.value or not app.packet_fingerprint:
        raise HTTPException(
            status_code=409, detail="Only an approved application with a current packet may run"
        )
    profile = await db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.id == app.candidate_profile_id,
            CandidateProfile.version == app.profile_version,
        )
    )
    job = await db.scalar(select(Job).where(Job.id == app.job_id))
    resume = await db.scalar(
        select(ApplicationMaterial)
        .where(ApplicationMaterial.application_id == app_id, ApplicationMaterial.kind == "resume")
        .order_by(ApplicationMaterial.version.desc())
    )
    cover = await db.scalar(
        select(ApplicationMaterial)
        .where(
            ApplicationMaterial.application_id == app_id,
            ApplicationMaterial.kind == "cover_letter",
        )
        .order_by(ApplicationMaterial.version.desc())
    )
    if profile is None or job is None or resume is None or cover is None:
        raise HTTPException(status_code=409, detail="Approved packet inputs are incomplete")

    contact = profile.contact_info or {}
    approved_fields = {
        key: str(value)
        for key, value in {
            "full_name": profile.full_name,
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "linkedin": contact.get("linkedin"),
            "resume": resume.content,
            "cover_letter": cover.content,
        }.items()
        if value not in (None, "")
    }
    target = mock_ats_url(job.source, job.external_id)
    return BrowserRunLaunchContextSchema(
        packet_fingerprint=app.packet_fingerprint or {},
        immutable_inputs=_expected_inputs(app),
        approved_fields=approved_fields,
        application_url=target,
        employer_url=job.source_url,
        mock_ats_label=MOCK_ATS_LABEL,
        planned_steps=build_plan(approved_fields, target),
    )


@router.post(
    "/{app_id}/browser-runs",
    response_model=BrowserRunSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_browser_run(
    app_id: str, body: BrowserRunStartRequest, db: AsyncSession = Depends(get_db)
) -> BrowserRunSchema:
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.APPROVED.value:
        raise HTTPException(
            status_code=409, detail="Only an approved application may start a browser run"
        )
    if app.packet_fingerprint != body.packet_fingerprint:
        raise HTTPException(
            status_code=409, detail="Packet fingerprint mismatch; re-approval is required"
        )
    if body.immutable_inputs != _expected_inputs(app):
        raise HTTPException(
            status_code=409,
            detail="Immutable application inputs do not match approved application",
        )

    try:
        # Rejects every non-sandbox destination, including employer URLs.
        assert_mock_target(body.application_url)
        plan = build_plan(body.approved_fields, body.application_url)
    except (MockAtsError, RunnerError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    run = BrowserRun(
        id=str(uuid.uuid4()),
        application_id=app.id,
        status="queued",
        packet_fingerprint=body.packet_fingerprint,
        immutable_inputs=body.immutable_inputs,
        approved_fields=body.approved_fields,
        headless=False,
        adapter_name=body.adapter,
        stopped_before_submit=False,
        mode="mock_sandbox",
        target_kind="mock_ats",
        target_url=body.application_url,
        plan=plan,
        cursor=0,
    )
    db.add(run)
    await db.flush()
    await _append_event(
        db,
        run.id,
        "run_queued",
        {
            "adapter": body.adapter,
            "headless": False,
            "target_kind": "mock_ats",
            "target_url": body.application_url,
            "planned_steps": len(plan),
            "label": MOCK_ATS_LABEL,
        },
    )
    await db.flush()
    return BrowserRunSchema.model_validate(await _reload(db, run.id))


@router.post("/{app_id}/browser-runs/{run_id}/advance", response_model=BrowserRunSchema)
async def advance_browser_run(
    app_id: str,
    run_id: str,
    body: BrowserRunAdvanceRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> BrowserRunSchema:
    """Execute the next planned step(s). Refuses to run while paused."""
    run = await _get_run(db, app_id, run_id)
    try:
        assert_advanceable(run.status)
    except RunnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    plan = [dict(cast(dict[str, Any], step)) for step in (run.plan or [])]
    requested = body.steps if body else 1
    approved_fields = dict(run.approved_fields or {})

    # Replay already-executed fills so the form state matches the persisted cursor.
    form_state: dict[str, str] = {}
    for step in plan[: run.cursor]:
        if step.get("action") == "fill":
            name = str((step.get("detail") or {}).get("field", ""))
            if name in approved_fields:
                form_state[name] = approved_fields[name]

    step_seq, event_seq = await _next_sequences(db, run_id)
    executed = 0
    cursor = run.cursor
    try:
        while executed < requested and cursor < len(plan):
            step_record, event_record, form_state = execute_step(
                plan[cursor], approved_fields, form_state
            )
            db.add(
                BrowserRunStep(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    sequence=step_seq,
                    action=step_record["action"],
                    detail=step_record["detail"],
                )
            )
            db.add(
                BrowserRunEvent(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    sequence=event_seq,
                    event_type=event_record["event_type"],
                    detail=event_record["detail"],
                )
            )
            step_seq += 1
            event_seq += 1
            cursor += 1
            executed += 1
    except RunnerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    run.cursor = cursor
    run.status = next_status(cursor, len(plan))
    if run.status == STOPPED_BEFORE_SUBMIT:
        run.stopped_before_submit = True
        run.completed_at = datetime.now(UTC)
        await _stop_application_before_submit(db, app_id)
    await db.flush()
    return BrowserRunSchema.model_validate(await _reload(db, run_id))


async def _stop_application_before_submit(db: AsyncSession, app_id: str) -> None:
    """Move the application to its terminal stop-before-submit state, once."""
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None or app.status != ApplicationStatus.APPROVED.value:
        return
    try:
        new_status = transition(
            ApplicationStatus.APPROVED,
            ApplicationStatus.STOPPED_BEFORE_SUBMIT,
            submission_mode=settings.initial_submission_mode,
        )
    except StateMachineError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(
        ApplicationEvent(
            id=str(uuid.uuid4()),
            application_id=app.id,
            from_status=app.status,
            to_status=new_status.value,
            triggered_by="system",
            note="Assisted run filled the approved fields and stopped before submission",
        )
    )
    app.status = new_status.value


@router.post("/{app_id}/browser-runs/{run_id}/pause", response_model=BrowserRunSchema)
async def pause_browser_run(
    app_id: str, run_id: str, db: AsyncSession = Depends(get_db)
) -> BrowserRunSchema:
    run = await _get_run(db, app_id, run_id)
    try:
        assert_pausable(run.status)
    except RunnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run.status = PAUSED
    run.paused_at = datetime.now(UTC)
    await _append_event(db, run_id, "run_paused", {"cursor": run.cursor})
    await db.flush()
    return BrowserRunSchema.model_validate(await _reload(db, run_id))


@router.post("/{app_id}/browser-runs/{run_id}/resume", response_model=BrowserRunSchema)
async def resume_browser_run(
    app_id: str, run_id: str, db: AsyncSession = Depends(get_db)
) -> BrowserRunSchema:
    run = await _get_run(db, app_id, run_id)
    try:
        assert_resumable(run.status)
    except RunnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run.status = RUNNING
    run.paused_at = None
    await _append_event(db, run_id, "run_resumed", {"cursor": run.cursor})
    await db.flush()
    return BrowserRunSchema.model_validate(await _reload(db, run_id))


@router.post(
    "/{app_id}/browser-runs/{run_id}/submit-to-mock-ats",
    response_model=MockAtsReceiptSchema,
    status_code=201,
)
async def submit_to_mock_ats(
    app_id: str, run_id: str, db: AsyncSession = Depends(get_db)
) -> MockAtsReceiptSchema:
    """
    Deliver the approved packet to the in-process mock ATS sandbox.

    This is the only submit action in CareerPilot and it can only reach the local
    sandbox board. The application stays at `stopped_before_submit`.
    """
    run = await _get_run(db, app_id, run_id)
    if run.mode != "mock_sandbox" or run.target_kind != "mock_ats":
        raise HTTPException(
            status_code=409, detail="Only a mock sandbox run may record a mock submission"
        )
    if run.status != STOPPED_BEFORE_SUBMIT:
        raise HTTPException(
            status_code=409,
            detail=(
                "Finish the assisted fill (the run stops before submit) "
                "before recording a mock submission"
            ),
        )
    try:
        board, external_job_id = assert_mock_target(run.target_url)
        fingerprint = run.packet_fingerprint or {}
        packet_hash = fingerprint.get("packet_hash")
        receipt, _ = await record_submission(
            db,
            board_token=board,
            external_job_id=external_job_id,
            application_id=app_id,
            payload=dict(run.approved_fields or {}),
            browser_run_id=run_id,
            packet_hash=str(packet_hash) if packet_hash else None,
        )
    except MockAtsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await _append_event(
        db,
        run_id,
        "mock_ats_submission_recorded",
        {
            "board_token": receipt.board_token,
            "confirmation_code": receipt.confirmation_code,
            "target_kind": "mock_ats",
            "label": MOCK_ATS_LABEL,
        },
    )
    await db.flush()
    return MockAtsReceiptSchema.model_validate(receipt)


@router.get("/{app_id}/browser-runs", response_model=list[BrowserRunSchema])
async def list_browser_runs(
    app_id: str, db: AsyncSession = Depends(get_db)
) -> list[BrowserRunSchema]:
    result = await db.execute(
        select(BrowserRun)
        .where(BrowserRun.application_id == app_id)
        .options(*_load_options())
        .order_by(BrowserRun.created_at.desc())
    )
    return [BrowserRunSchema.model_validate(item) for item in result.scalars().all()]


@router.get("/{app_id}/mock-ats-submissions", response_model=list[MockAtsReceiptSchema])
async def list_application_receipts(
    app_id: str, db: AsyncSession = Depends(get_db)
) -> list[MockAtsReceiptSchema]:
    """Sandbox receipts recorded for this application."""
    result = await db.execute(
        select(MockAtsSubmission)
        .where(MockAtsSubmission.application_id == app_id)
        .order_by(MockAtsSubmission.received_at.desc())
    )
    return [MockAtsReceiptSchema.model_validate(item) for item in result.scalars().all()]


@router.get("/{app_id}/browser-runs/{run_id}", response_model=BrowserRunSchema)
async def get_browser_run(
    app_id: str, run_id: str, db: AsyncSession = Depends(get_db)
) -> BrowserRunSchema:
    return BrowserRunSchema.model_validate(await _get_run(db, app_id, run_id))


@router.post("/{app_id}/browser-runs/{run_id}/approval-token", status_code=status.HTTP_201_CREATED)
async def issue_approval_token(
    app_id: str,
    run_id: str,
    body: ApprovalTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Compatibility token endpoint; never drives a real employer page."""
    if settings.initial_submission_mode != "allow_submit":
        raise HTTPException(status_code=409, detail="submission is disabled")
    if not settings.approval_signing_secret:
        raise HTTPException(status_code=409, detail="approval signing secret is not configured")
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.APPROVED.value or not app.packet_fingerprint:
        raise HTTPException(status_code=409, detail="Only an approved application may be submitted")
    run = await db.scalar(select(BrowserRun).where(BrowserRun.id == run_id, BrowserRun.application_id == app_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Browser run not found")
    if run.status != "stopped_at_review" or not run.final_page_fingerprint:
        raise HTTPException(status_code=409, detail="Run has not stopped at a reviewed final page")
    if run.final_page_fingerprint != body.final_page_fingerprint:
        raise HTTPException(status_code=409, detail="Final-page fingerprint changed since review")
    if run.submitted:
        raise HTTPException(status_code=409, detail="Application already submitted")
    expected_resume = int(str(app.packet_fingerprint.get("resume_version", -1)))
    if body.resume_version != expected_resume:
        raise HTTPException(status_code=409, detail="Resume version does not match the approved packet")
    existing = await db.scalar(select(ApprovalToken).where(ApprovalToken.browser_run_id == run_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An approval token has already been issued for this run")
    answer_versions = app.packet_fingerprint.get("answer_versions", {})
    answer_set_version = max((int(value) for value in answer_versions.values()), default=0) if isinstance(answer_versions, dict) else 0
    binding = ApprovalBinding(app_id, app.job_id, expected_resume, answer_set_version, run_id, run.final_page_fingerprint)
    token_id = uuid.uuid4().hex
    token = issue_token(token_id, binding, secret=settings.approval_signing_secret)
    db.add(ApprovalToken(application_id=app_id, browser_run_id=run_id, token_id=token_id, binding_digest=binding.digest(), resume_version=expected_resume, answer_set_version=answer_set_version, final_page_fingerprint=run.final_page_fingerprint, consumed=False))
    await db.flush()
    return {"token": token, "token_id": token_id, "application_id": app_id, "browser_run_id": run_id, "resume_version": expected_resume, "answer_set_version": answer_set_version, "final_page_fingerprint": run.final_page_fingerprint, "binding_digest": binding.digest(), "consumed": False}
