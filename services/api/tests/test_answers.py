from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.models.material import AnswerLibraryEntry
from app.models.profile import CandidateProfile


@pytest.fixture(autouse=True)
async def cleanup_answer_rows(db_session):
    yield
    await db_session.execute(delete(AnswerLibraryEntry))
    await db_session.execute(delete(CandidateProfile))
    await db_session.commit()


def test_answer_library_rejects_empty_answer() -> None:
    from app.materials.answers import validate_answer

    with pytest.raises(ValueError, match="answer"):
        validate_answer("   ")


@pytest.mark.asyncio
async def test_answer_library_versions_answers_and_lists(client, db_session) -> None:
    from app.models.profile import CandidateProfile

    profile_id = str(uuid.uuid4())
    db_session.add(CandidateProfile(id=profile_id, version=1, full_name="Ada", skills=[]))
    await db_session.commit()
    first = await client.post(
        "/api/v1/answers",
        json={
            "candidate_profile_id": profile_id,
            "question_key": "work_auth",
            "question": "Authorized?",
            "answer": "Yes",
            "reviewed": True,
        },
    )
    assert first.status_code == 201
    assert first.json()["version"] == 1
    second = await client.post(
        "/api/v1/answers",
        json={
            "candidate_profile_id": profile_id,
            "question_key": "work_auth",
            "question": "Authorized?",
            "answer": "Yes, I am authorized.",
            "reviewed": False,
        },
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2
    listed = await client.get(f"/api/v1/answers?candidate_profile_id={profile_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
