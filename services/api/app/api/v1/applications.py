from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.application import Application, ApplicationEvent
from app.schemas.application import (
    ApplicationSchema,
    ApplicationSummarySchema,
    TransitionRequestSchema,
)
from app.state_machine.application import (
    ApplicationStatus,
    StateMachineError,
    SubmissionBlockedError,
    transition,
)

router = APIRouter()


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
async def get_application(
    app_id: str, db: AsyncSession = Depends(get_db)
) -> ApplicationSchema:
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
