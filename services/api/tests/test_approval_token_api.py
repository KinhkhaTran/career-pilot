from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.approval import ApprovalBinding, issue_token
from app.config import settings
from app.models.application import Application
from app.models.browser_run import ApprovalToken, BrowserRun
from app.models.job import Job
from app.models.profile import CandidateProfile


@pytest.fixture(autouse=True)
async def cleanup(db_session):
    yield
    await db_session.execute(delete(ApprovalToken))
    await db_session.execute(delete(BrowserRun))
    await db_session.execute(delete(Application))
    await db_session.execute(delete(Job))
    await db_session.execute(delete(CandidateProfile))
    await db_session.commit()


@pytest.fixture(autouse=True)
def enable_submission(monkeypatch):
    monkeypatch.setattr(settings, "initial_submission_mode", "allow_submit")
    monkeypatch.setattr(settings, "approval_signing_secret", "unit-test-secret")


FINGERPRINT = "a" * 64


async def _seed_review_run(db_session) -> tuple[str, str]:
    profile_id, job_id, app_id, run_id = (str(uuid.uuid4()) for _ in range(4))
    packet = {"profile_version": 1, "resume_version": 1, "answer_versions": {"q1": 2}, "packet_hash": "p"}
    db_session.add_all(
        [
            CandidateProfile(id=profile_id, version=1, full_name="Ada", summary="x", skills=[], work_experience=[]),
            Job(id=job_id, external_id="j1", source="fake", source_url="https://jobs.invalid/1", title="Eng", company="Acme", description="d", snapshot_hash="h"),
            Application(id=app_id, job_id=job_id, candidate_profile_id=profile_id, profile_version=1, job_snapshot_hash="h", job_snapshot={"t": "e"}, status="approved", packet_fingerprint=packet),
            BrowserRun(id=run_id, application_id=app_id, status="stopped_at_review", packet_fingerprint=packet, immutable_inputs={}, approved_fields={}, headless=False, adapter_name="workday", final_page_fingerprint=FINGERPRINT, submission_mode="allow_submit"),
        ]
    )
    await db_session.commit()
    return app_id, run_id


def test_token_algorithm_parity_vector() -> None:
    """Same fixed vector as the worker's test — guards against cross-service drift."""
    b = ApprovalBinding("app-1", "job-1", 3, 2, "run-1", "fp-abc")
    token = issue_token("tok-1", b, secret="parity-secret")
    assert token == "tok-1.490160f48976a44685a6410024393b7053a268e92614fc66c8fdbac949c4bb8b"


async def test_issues_one_time_token_for_reviewed_run(client, db_session) -> None:
    app_id, run_id = await _seed_review_run(db_session)
    body = {"final_page_fingerprint": FINGERPRINT, "resume_version": 1, "confirm": True}

    res = await client.post(f"/api/v1/applications/{app_id}/browser-runs/{run_id}/approval-token", json=body)
    assert res.status_code == 201
    data = res.json()
    assert data["token"].startswith(data["token_id"])
    assert data["final_page_fingerprint"] == FINGERPRINT
    assert data["consumed"] is False

    # One-time issuance: a second request for the same run is refused.
    again = await client.post(f"/api/v1/applications/{app_id}/browser-runs/{run_id}/approval-token", json=body)
    assert again.status_code == 409


async def test_rejects_changed_fingerprint_and_unconfirmed(client, db_session) -> None:
    app_id, run_id = await _seed_review_run(db_session)
    base = f"/api/v1/applications/{app_id}/browser-runs/{run_id}/approval-token"

    changed = await client.post(base, json={"final_page_fingerprint": "b" * 64, "resume_version": 1, "confirm": True})
    assert changed.status_code == 409

    unconfirmed = await client.post(base, json={"final_page_fingerprint": FINGERPRINT, "resume_version": 1, "confirm": False})
    assert unconfirmed.status_code == 422


async def test_blocked_when_mode_not_allow_submit(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "initial_submission_mode", "stop_before_submit")
    app_id, run_id = await _seed_review_run(db_session)
    res = await client.post(
        f"/api/v1/applications/{app_id}/browser-runs/{run_id}/approval-token",
        json={"final_page_fingerprint": FINGERPRINT, "resume_version": 1, "confirm": True},
    )
    assert res.status_code == 409
