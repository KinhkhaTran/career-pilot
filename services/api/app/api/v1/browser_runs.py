from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.approval import ApprovalBinding, issue_token
from app.config import settings
from app.database import get_db
from app.models.application import Application
from app.models.browser_run import ApprovalToken, BrowserRun
from app.models.job import Job
from app.models.material import ApplicationMaterial
from app.models.profile import CandidateProfile
from app.schemas.browser_run import (
    ApprovalTokenRequest,
    ApprovalTokenSchema,
    BrowserRunLaunchContextSchema,
    BrowserRunSchema,
    BrowserRunStartRequest,
)
from app.state_machine.application import ApplicationStatus

router = APIRouter()


def _answer_set_version(packet_fingerprint: dict[str, Any]) -> int:
    """Deterministic integer version of the approved answer set.

    Computed identically wherever needed so the API-minted token and the
    worker-side binding agree without recomputation drift.
    """
    answers = packet_fingerprint.get("answer_versions", {})
    basis = json.dumps(answers, sort_keys=True, separators=(",", ":"))
    return int(hashlib.sha256(basis.encode()).hexdigest()[:8], 16)


def _load_options() -> tuple[Any, ...]:
    return (
        selectinload(BrowserRun.steps),
        selectinload(BrowserRun.events),
        selectinload(BrowserRun.screenshots),
    )


@router.get("/{app_id}/browser-runs/launch-context", response_model=BrowserRunLaunchContextSchema)
async def get_launch_context(
    app_id: str, db: AsyncSession = Depends(get_db)
) -> BrowserRunLaunchContextSchema:
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.APPROVED.value or not app.packet_fingerprint:
        raise HTTPException(status_code=409, detail="Only an approved application with a current packet may run")
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
        .where(ApplicationMaterial.application_id == app_id, ApplicationMaterial.kind == "cover_letter")
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
    immutable_inputs = {
        "profile_version": app.profile_version,
        "job_snapshot_hash": app.job_snapshot_hash,
        "job_snapshot": app.job_snapshot,
        "packet_fingerprint": app.packet_fingerprint,
    }
    return BrowserRunLaunchContextSchema(
        packet_fingerprint=app.packet_fingerprint,
        immutable_inputs=immutable_inputs,
        approved_fields=approved_fields,
        application_url=job.source_url,
    )


@router.post("/{app_id}/browser-runs", response_model=BrowserRunSchema, status_code=status.HTTP_202_ACCEPTED)
async def start_browser_run(app_id: str, body: BrowserRunStartRequest, db: AsyncSession = Depends(get_db)) -> BrowserRunSchema:
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail="Only an approved application may start a browser run")
    if app.packet_fingerprint != body.packet_fingerprint:
        raise HTTPException(status_code=409, detail="Packet fingerprint mismatch; re-approval is required")
    expected_inputs = {
        "profile_version": app.profile_version,
        "job_snapshot_hash": app.job_snapshot_hash,
        "job_snapshot": app.job_snapshot,
        "packet_fingerprint": app.packet_fingerprint,
    }
    if body.immutable_inputs != expected_inputs:
        raise HTTPException(status_code=409, detail="Immutable application inputs do not match approved application")
    run = BrowserRun(
        application_id=app.id,
        status="queued",
        packet_fingerprint=body.packet_fingerprint,
        immutable_inputs=body.immutable_inputs,
        approved_fields=body.approved_fields,
        headless=False,
        adapter_name=body.adapter,
        stopped_before_submit=False,
    )
    db.add(run)
    await db.flush()
    result = await db.execute(
        select(BrowserRun).where(BrowserRun.id == run.id).options(*_load_options())
    )
    persisted = result.scalar_one()
    return BrowserRunSchema.model_validate(persisted)


@router.get("/{app_id}/browser-runs", response_model=list[BrowserRunSchema])
async def list_browser_runs(app_id: str, db: AsyncSession = Depends(get_db)) -> list[BrowserRunSchema]:
    result = await db.execute(
        select(BrowserRun).where(BrowserRun.application_id == app_id)
        .options(*_load_options()).order_by(BrowserRun.created_at.desc())
    )
    return [BrowserRunSchema.model_validate(item) for item in result.scalars().all()]


@router.post(
    "/{app_id}/browser-runs/{run_id}/approval-token",
    response_model=ApprovalTokenSchema,
    status_code=status.HTTP_201_CREATED,
)
async def issue_approval_token(
    app_id: str,
    run_id: str,
    body: ApprovalTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> ApprovalTokenSchema:
    """Mint a single-use token authorising exactly one Submit click (requirement 12).

    Guarded on: the opt-in ``allow_submit`` mode, an approved application, a run
    that has stopped at the Review page with a final-page fingerprint the human
    is confirming, and no previously-issued token for this run.
    """
    if settings.initial_submission_mode != "allow_submit":
        raise HTTPException(
            status_code=409,
            detail="submission is disabled; INITIAL_SUBMISSION_MODE is not 'allow_submit'",
        )
    if not settings.approval_signing_secret:
        raise HTTPException(status_code=409, detail="approval signing secret is not configured")

    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != ApplicationStatus.APPROVED.value or not app.packet_fingerprint:
        raise HTTPException(status_code=409, detail="Only an approved application may be submitted")

    run = await db.scalar(
        select(BrowserRun).where(BrowserRun.id == run_id, BrowserRun.application_id == app_id)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Browser run not found")
    if run.status != "stopped_at_review" or not run.final_page_fingerprint:
        raise HTTPException(
            status_code=409, detail="Run has not stopped at a reviewed final page"
        )
    if run.final_page_fingerprint != body.final_page_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Final-page fingerprint changed since review; re-review is required",
        )
    if run.submitted:
        raise HTTPException(status_code=409, detail="Application already submitted")

    fingerprint = app.packet_fingerprint
    expected_resume = int(str(fingerprint.get("resume_version", -1)))
    if body.resume_version != expected_resume:
        raise HTTPException(
            status_code=409, detail="Résumé version does not match the approved packet"
        )

    existing = await db.scalar(
        select(ApprovalToken).where(ApprovalToken.browser_run_id == run_id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="An approval token has already been issued for this run"
        )

    answer_set_version = _answer_set_version(fingerprint)
    binding = ApprovalBinding(
        application_id=app_id,
        job_id=app.job_id,
        resume_version=expected_resume,
        answer_set_version=answer_set_version,
        browser_run_id=run_id,
        final_page_fingerprint=run.final_page_fingerprint,
    )
    token_id = uuid.uuid4().hex
    token = issue_token(token_id, binding, secret=settings.approval_signing_secret)

    record = ApprovalToken(
        application_id=app_id,
        browser_run_id=run_id,
        token_id=token_id,
        binding_digest=binding.digest(),
        resume_version=expected_resume,
        answer_set_version=answer_set_version,
        final_page_fingerprint=run.final_page_fingerprint,
        consumed=False,
    )
    db.add(record)
    await db.flush()
    return ApprovalTokenSchema(
        id=record.id,
        token=token,
        token_id=token_id,
        application_id=app_id,
        browser_run_id=run_id,
        resume_version=expected_resume,
        answer_set_version=answer_set_version,
        final_page_fingerprint=run.final_page_fingerprint,
        binding_digest=binding.digest(),
        consumed=False,
        created_at=None,
    )


@router.get("/{app_id}/browser-runs/{run_id}", response_model=BrowserRunSchema)
async def get_browser_run(app_id: str, run_id: str, db: AsyncSession = Depends(get_db)) -> BrowserRunSchema:
    result = await db.execute(
        select(BrowserRun).where(BrowserRun.id == run_id, BrowserRun.application_id == app_id)
        .options(*_load_options())
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Browser run not found")
    return BrowserRunSchema.model_validate(run)
