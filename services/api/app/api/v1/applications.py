from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.materials import build_packet_fingerprint, tailor_resume, unified_diff
from app.models.application import Application, ApplicationEvent
from app.models.job import Job
from app.models.material import AnswerLibraryEntry, ApplicationMaterial
from app.models.profile import CandidateProfile
from app.schemas.application import (
    ApplicationSchema,
    ApplicationSummarySchema,
    TransitionRequestSchema,
)
from app.schemas.material import (
    AnswerSchema,
    GenerateMaterialsRequest,
    MaterialSchema,
    PacketResponseSchema,
    ReviewRequestSchema,
)
from app.state_machine.application import (
    ApplicationStatus,
    StateMachineError,
    SubmissionBlockedError,
    transition,
)

router = APIRouter()


@router.post("/{app_id}/materials/generate", response_model=PacketResponseSchema, status_code=201)
async def generate_materials(
    app_id: str,
    body: GenerateMaterialsRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> PacketResponseSchema:
    """Generate a truthful packet from immutable application inputs."""
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    if app.status != ApplicationStatus.MATCHED.value:
        raise HTTPException(status_code=409, detail="Materials can only be generated from a matched application")
    job = await db.scalar(select(Job).where(Job.id == app.job_id))
    if app.profile_version is None or app.job_snapshot is None:
        profile = await db.scalar(
            select(CandidateProfile)
            .where(CandidateProfile.id == app.candidate_profile_id)
            .order_by(CandidateProfile.version.desc())
        )
        if job is None or profile is None:
            raise HTTPException(status_code=409, detail="Application inputs are incomplete")
        app.profile_version = profile.version
        app.job_snapshot_hash = job.snapshot_hash
        app.job_snapshot = {
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "snapshot_hash": job.snapshot_hash,
        }
    else:
        profile = await db.scalar(
            select(CandidateProfile).where(
                CandidateProfile.id == app.candidate_profile_id,
                CandidateProfile.version == app.profile_version,
            )
        )
        if profile is None:
            raise HTTPException(status_code=409, detail="Pinned candidate profile version is unavailable")
        job_snapshot = app.job_snapshot
        job = type("JobSnapshot", (), job_snapshot)()

    answer_keys = (body.answer_keys if body else [])
    answers: list[AnswerLibraryEntry] = []
    if answer_keys:
        rows = (
            await db.scalars(
                select(AnswerLibraryEntry)
                .where(
                    AnswerLibraryEntry.candidate_profile_id == app.candidate_profile_id,
                    AnswerLibraryEntry.question_key.in_(answer_keys),
                )
                .order_by(AnswerLibraryEntry.question_key, AnswerLibraryEntry.version.desc())
            )
        ).all()
        latest: dict[str, AnswerLibraryEntry] = {}
        for row in rows:
            latest.setdefault(row.question_key, row)
        missing = set(answer_keys) - latest.keys()
        if missing:
            raise HTTPException(status_code=409, detail=f"Answer keys unavailable: {sorted(missing)}")
        answers = [latest[key] for key in answer_keys]

    tailored = tailor_resume(
        {"summary": profile.summary, "skills": profile.skills, "work_experience": profile.work_experience},
        {"title": job.title, "description": job.description},
    )
    cover = f"Dear {job.company} hiring team,\n\nI am interested in the {job.title} role.\n\n{profile.summary or ''}\n\nSincerely,\n{profile.full_name}"
    previous_resume = await db.scalar(
        select(ApplicationMaterial)
        .where(ApplicationMaterial.application_id == app_id, ApplicationMaterial.kind == "resume")
        .order_by(ApplicationMaterial.version.desc())
    )
    resume_version = (previous_resume.version + 1) if previous_resume else 1
    resume = ApplicationMaterial(
        application_id=app_id,
        kind="resume",
        version=resume_version,
        content=tailored.text,
        diff=None if previous_resume is None else unified_diff(previous_resume.content, tailored.text),
        source_claims=tailored.source_claims,
    )
    letter = ApplicationMaterial(
        application_id=app_id,
        kind="cover_letter",
        version=resume_version,
        content=cover,
        source_claims=[profile.full_name, job.title, job.company],
    )
    db.add_all([resume, letter])
    answer_versions = {answer.question_key: answer.version for answer in answers}
    rendered_answers = "\n".join(f"Q: {answer.question}\nA: {answer.answer}" for answer in answers)
    fingerprint = build_packet_fingerprint(
        profile_version=profile.version,
        resume_version=resume_version,
        answer_versions=answer_versions,
        job_snapshot_hash=app.job_snapshot_hash or job.snapshot_hash,
        rendered_packet=f"{tailored.text}\n{cover}\n{rendered_answers}",
        cover_letter_version=resume_version,
    )
    app.packet_fingerprint = fingerprint
    for target in (
        ApplicationStatus.PACKET_DRAFT,
        ApplicationStatus.PACKET_READY,
        ApplicationStatus.HUMAN_REVIEW,
    ):
        current = ApplicationStatus(app.status)
        new_status = transition(current, target, submission_mode=settings.initial_submission_mode)
        db.add(
            ApplicationEvent(
                id=str(uuid.uuid4()), application_id=app.id, from_status=current.value,
                to_status=new_status.value, triggered_by="system", note="Materials generated",
            )
        )
        app.status = new_status.value
    await db.flush()
    return PacketResponseSchema(
        resume=MaterialSchema.model_validate(resume),
        cover_letter=MaterialSchema.model_validate(letter),
        answers=[AnswerSchema.model_validate(answer) for answer in answers],
        fingerprint=fingerprint,
    )


@router.get("/{app_id}/materials", response_model=list[MaterialSchema])
async def list_materials(app_id: str, db: AsyncSession = Depends(get_db)) -> list[MaterialSchema]:
    materials = (
        await db.scalars(
            select(ApplicationMaterial)
            .where(ApplicationMaterial.application_id == app_id)
            .order_by(ApplicationMaterial.version, ApplicationMaterial.kind)
        )
    ).all()
    return [MaterialSchema.model_validate(material) for material in materials]


@router.post("/{app_id}/review", response_model=ApplicationSchema)
async def review_application(
    app_id: str, body: ReviewRequestSchema, db: AsyncSession = Depends(get_db)
) -> ApplicationSchema:
    if body.decision != "approve":
        raise HTTPException(
            status_code=422, detail="Only approve is supported by the initial release"
        )
    stmt = (
        select(Application)
        .where(Application.id == app_id)
        .options(selectinload(Application.events))
    )
    app = (await db.execute(stmt)).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    if not app.packet_fingerprint or app.status != ApplicationStatus.HUMAN_REVIEW.value:
        raise HTTPException(
            status_code=409, detail="A current generated packet must be in human review"
        )
    materials = (
        await db.scalars(
            select(ApplicationMaterial).where(ApplicationMaterial.application_id == app.id)
        )
    ).all()
    if not materials:
        raise HTTPException(status_code=409, detail="No generated materials are available for review")
    current_status = ApplicationStatus(app.status)
    try:
        new_status = transition(
            current_status,
            ApplicationStatus.APPROVED,
            submission_mode=settings.initial_submission_mode,
        )
    except StateMachineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for material in materials:
        material.reviewed = True
    app.status = new_status.value
    db.add(
        ApplicationEvent(
            id=str(uuid.uuid4()),
            application_id=app.id,
            from_status=current_status.value,
            to_status=new_status.value,
            triggered_by="human",
            note=body.note,
        )
    )
    await db.flush()
    await db.refresh(app)
    return ApplicationSchema.model_validate(app)


@router.get("", response_model=list[ApplicationSummarySchema])
async def list_applications(
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationSummarySchema]:
    """List all applications (summary view)."""
    stmt = select(Application).order_by(Application.created_at.desc())
    result = await db.execute(stmt)
    apps = result.scalars().all()
    return [ApplicationSummarySchema.model_validate(a) for a in apps]


@router.get("/{app_id}", response_model=ApplicationSchema)
async def get_application(app_id: str, db: AsyncSession = Depends(get_db)) -> ApplicationSchema:
    """Return a single application with its full event history."""
    stmt = (
        select(Application)
        .where(Application.id == app_id)
        .options(selectinload(Application.events))
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")
    return ApplicationSchema.model_validate(app)


@router.post("/{app_id}/transition", response_model=ApplicationSchema)
async def transition_application(
    app_id: str,
    body: TransitionRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> ApplicationSchema:
    """
    Attempt a state transition on an application.

    Returns 409 Conflict on:
    - Invalid transition for the current state.
    - Transition to SUBMITTED when INITIAL_SUBMISSION_MODE=stop_before_submit.
    """
    stmt = (
        select(Application)
        .where(Application.id == app_id)
        .options(selectinload(Application.events))
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id!r} not found")

    current_status = ApplicationStatus(app.status)
    target_status = body.target_status

    try:
        new_status = transition(
            current_status,
            target_status,
            submission_mode=settings.initial_submission_mode,
        )
    except SubmissionBlockedError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "submission_blocked",
                "message": str(exc),
                "current_status": current_status.value,
                "target_status": target_status.value,
                "submission_mode": settings.initial_submission_mode,
            },
        ) from exc
    except StateMachineError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "invalid_transition",
                "message": str(exc),
                "current_status": current_status.value,
                "target_status": target_status.value,
            },
        ) from exc

    # Record the transition
    from_status_str = app.status
    app.status = new_status.value

    event = ApplicationEvent(
        id=str(uuid.uuid4()),
        application_id=app.id,
        from_status=from_status_str,
        to_status=new_status.value,
        triggered_by="human",
        note=body.note,
    )
    db.add(event)
    await db.flush()
    await db.refresh(app)

    # Reload with events for the response
    stmt2 = (
        select(Application)
        .where(Application.id == app_id)
        .options(selectinload(Application.events))
    )
    result2 = await db.execute(stmt2)
    updated_app = result2.scalar_one()
    return ApplicationSchema.model_validate(updated_app)
