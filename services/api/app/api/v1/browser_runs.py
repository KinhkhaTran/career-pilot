from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.application import Application
from app.models.browser_run import BrowserRun
from app.schemas.browser_run import BrowserRunSchema, BrowserRunStartRequest
from app.state_machine.application import ApplicationStatus

router = APIRouter()


def _load_options() -> tuple[Any, ...]:
    return (
        selectinload(BrowserRun.steps),
        selectinload(BrowserRun.events),
        selectinload(BrowserRun.screenshots),
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
