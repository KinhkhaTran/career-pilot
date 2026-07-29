from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.models.application import Application
from app.models.browser_run import BrowserRun, BrowserRunEvent, BrowserRunStep, BrowserScreenshot
from app.models.job import Job
from app.models.profile import CandidateProfile


@pytest.fixture(autouse=True)
async def cleanup_browser_runs(db_session):
    yield
    await db_session.execute(delete(BrowserRunEvent))
    await db_session.execute(delete(BrowserRunStep))
    await db_session.execute(delete(BrowserScreenshot))
    await db_session.execute(delete(BrowserRun))
    await db_session.execute(delete(Application))
    await db_session.execute(delete(Job))
    await db_session.execute(delete(CandidateProfile))
    await db_session.commit()


def approved_application() -> tuple[CandidateProfile, Job, Application, dict[str, object]]:
    profile_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    app_id = str(uuid.uuid4())
    fingerprint = {
        "profile_version": 1,
        "resume_version": 1,
        "cover_letter_version": 1,
        "answer_versions": {},
        "job_snapshot_hash": "job-hash",
        "packet_hash": "packet-hash",
    }
    snapshot = {"title": "Engineer", "company": "Acme", "description": "Build systems"}
    profile = CandidateProfile(
        id=profile_id,
        version=1,
        full_name="Ada Lovelace",
        summary="Engineer",
        skills=["Python"],
        work_experience=[],
    )
    job = Job(
        id=job_id,
        external_id="job-browser-1",
        source="fake",
        source_url="https://jobs.invalid/1",
        title="Engineer",
        company="Acme",
        description="Build systems",
        snapshot_hash="job-hash",
    )
    application = Application(
        id=app_id,
        job_id=job_id,
        candidate_profile_id=profile_id,
        profile_version=1,
        job_snapshot_hash="job-hash",
        job_snapshot=snapshot,
        status="approved",
        packet_fingerprint=fingerprint,
    )
    return profile, job, application, fingerprint


@pytest.mark.asyncio
async def test_browser_run_requires_approval_and_exact_binding(client, db_session) -> None:
    profile, job, application, fingerprint = approved_application()
    db_session.add_all([profile, job, application])
    await db_session.commit()
    inputs = {
        "profile_version": 1,
        "job_snapshot_hash": "job-hash",
        "job_snapshot": application.job_snapshot,
        "packet_fingerprint": fingerprint,
    }
    payload = {
        "packet_fingerprint": fingerprint,
        "immutable_inputs": inputs,
        "approved_fields": {"full_name": "Ada Lovelace"},
        "application_url": "mock-ats://fake-mock/job-browser-1",
    }

    started = await client.post(f"/api/v1/applications/{application.id}/browser-runs", json=payload)
    assert started.status_code == 202
    assert started.json()["status"] == "queued"
    assert started.json()["headless"] is False

    mismatch = {**payload, "packet_fingerprint": {"packet_hash": "wrong"}}
    rejected = await client.post(f"/api/v1/applications/{application.id}/browser-runs", json=mismatch)
    assert rejected.status_code == 409

    payload["headless"] = True
    headless = await client.post(f"/api/v1/applications/{application.id}/browser-runs", json=payload)
    assert headless.status_code == 422


@pytest.mark.asyncio
async def test_browser_run_rejects_unapproved_application(client, db_session) -> None:
    profile, job, application, fingerprint = approved_application()
    application.status = "human_review"
    db_session.add_all([profile, job, application])
    await db_session.commit()
    inputs = {
        "profile_version": 1,
        "job_snapshot_hash": "job-hash",
        "job_snapshot": application.job_snapshot,
        "packet_fingerprint": fingerprint,
    }
    response = await client.post(
        f"/api/v1/applications/{application.id}/browser-runs",
        json={
            "packet_fingerprint": fingerprint,
            "immutable_inputs": inputs,
            "approved_fields": {"password": "never"},
            "application_url": "mock-ats://fake-mock/job-browser-1",
        },
    )
    assert response.status_code in {409, 422}
