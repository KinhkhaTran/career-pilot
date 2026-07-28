from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.materials.packet import build_packet_fingerprint
from app.materials.tailoring import tailor_resume, unified_diff
from app.models.application import Application
from app.models.job import Job
from app.models.material import AnswerLibraryEntry, ApplicationMaterial
from app.models.profile import CandidateProfile


@pytest.fixture(autouse=True)
async def cleanup_material_rows(db_session):
    yield
    await db_session.execute(delete(AnswerLibraryEntry))
    await db_session.execute(delete(ApplicationMaterial))
    await db_session.execute(delete(Application))
    await db_session.execute(delete(Job))
    await db_session.execute(delete(CandidateProfile))
    await db_session.commit()


def test_tailoring_only_selects_existing_profile_claims() -> None:
    profile = {
        "summary": "Backend engineer building reliable APIs.",
        "work_experience": [
            {
                "company": "Acme",
                "title": "Engineer",
                "achievements": ["Reduced latency by 40%", "Mentored 3 engineers"],
            },
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
    }
    job = {
        "title": "Senior Python Engineer",
        "description": "Build FastAPI services with PostgreSQL.",
    }

    result = tailor_resume(profile, job)

    assert "Reduced latency by 40%" in result.text
    assert "Mentored 3 engineers" in result.text
    assert result.added_claims == []
    assert result.source_claims == ["Reduced latency by 40%", "Mentored 3 engineers"]


def test_unified_diff_marks_material_changes() -> None:
    diff = unified_diff("Summary\nPython", "Summary\nPython\nFastAPI")
    assert "+++ tailored" in diff
    assert "+FastAPI" in diff


def test_packet_fingerprint_is_deterministic_and_binds_all_inputs() -> None:
    first = build_packet_fingerprint(
        profile_version=2,
        resume_version=3,
        answer_versions={"work_auth": 1},
        job_snapshot_hash="job-hash",
        rendered_packet="resume\ncover\nanswer",
    )
    second = build_packet_fingerprint(
        profile_version=2,
        resume_version=3,
        answer_versions={"work_auth": 1},
        job_snapshot_hash="job-hash",
        rendered_packet="resume\ncover\nanswer",
    )
    changed = build_packet_fingerprint(
        profile_version=2,
        resume_version=4,
        answer_versions={"work_auth": 1},
        job_snapshot_hash="job-hash",
        rendered_packet="resume\ncover\nanswer",
    )

    assert first == second
    assert first["packet_hash"] != changed["packet_hash"]
    assert first["profile_version"] == 2
    assert first["resume_version"] == 3


@pytest.mark.asyncio
async def test_materials_endpoint_generates_packet_and_review_gate(client, db_session) -> None:
    from app.models.application import Application
    from app.models.job import Job
    from app.models.profile import CandidateProfile

    profile_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    app_id = str(uuid.uuid4())
    db_session.add(
        CandidateProfile(
            id=profile_id,
            version=1,
            full_name="Ada Lovelace",
            summary="Python engineer",
            skills=["Python"],
            work_experience=[],
        )
    )
    db_session.add(
        Job(
            id=job_id,
            external_id="job-1",
            source="fake",
            source_url="https://jobs.invalid/1",
            title="Python Engineer",
            company="Acme",
            description="Build Python systems",
            snapshot_hash="job-hash",
            requirements=["Python"],
        )
    )
    db_session.add(
        Application(id=app_id, job_id=job_id, candidate_profile_id=profile_id, status="matched")
    )
    db_session.add(
        AnswerLibraryEntry(
            id=str(uuid.uuid4()),
            candidate_profile_id=profile_id,
            question_key="work_auth",
            question="Are you authorized to work?",
            answer="Yes, I am authorized to work in the United States.",
            version=1,
            reviewed=True,
        )
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/applications/{app_id}/materials/generate",
        json={"answer_keys": ["work_auth"]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["resume"]["content"]
    assert payload["cover_letter"]["content"]
    assert payload["fingerprint"]["job_snapshot_hash"] == "job-hash"
    assert payload["fingerprint"]["cover_letter_version"] == 1
    assert payload["fingerprint"]["answer_versions"] == {"work_auth": 1}
    assert payload["answers"][0]["question_key"] == "work_auth"

    review = await client.post(
        f"/api/v1/applications/{app_id}/review", json={"decision": "approve", "note": "Reviewed"}
    )
    assert review.status_code == 200
    assert review.json()["status"] == "approved"
    transitions = [(event["from_status"], event["to_status"]) for event in review.json()["events"]]
    assert ("matched", "packet_draft") in transitions
    assert ("packet_draft", "packet_ready") in transitions
    assert ("packet_ready", "human_review") in transitions
    listed_materials = await client.get(f"/api/v1/applications/{app_id}/materials")
    assert listed_materials.status_code == 200
    assert all(item["reviewed"] for item in listed_materials.json())

    stale = await client.post(f"/api/v1/applications/{app_id}/review", json={"decision": "approve"})
    assert stale.status_code == 409
    regenerate = await client.post(f"/api/v1/applications/{app_id}/materials/generate")
    assert regenerate.status_code == 409
