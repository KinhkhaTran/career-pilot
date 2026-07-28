import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.models.job import Job
from app.models.match import Match
from app.models.profile import CandidateProfile


@pytest.fixture(autouse=True)
async def cleanup_match_data(db_session):
    yield
    await db_session.execute(delete(Match))
    await db_session.execute(delete(Job))
    await db_session.execute(delete(CandidateProfile))
    await db_session.commit()


async def _seed_match_inputs(db_session):
    profile_id = str(uuid.uuid4())
    await db_session.merge(
        CandidateProfile(
            id=profile_id,
            version=1,
            full_name="Alex Example",
            contact_info={"location": "Boston, MA"},
            summary="Backend engineer",
            skills=["Python", "FastAPI"],
            work_experience=[{"title": "Python Engineer"}],
            education=[],
            certifications=[],
            languages=[],
        )
    )
    job_id = str(uuid.uuid4())
    await db_session.merge(
        Job(
            id=job_id,
            external_id=f"job-{job_id}",
            source="direct",
            source_url=f"https://jobs.invalid/{job_id}",
            title="Python Engineer",
            company="Example",
            location="Boston, MA",
            is_remote=False,
            employment_type="full_time",
            description="Build APIs",
            requirements=["Python"],
            nice_to_have=[],
            technologies=["FastAPI"],
            snapshot_hash="hash-1",
        )
    )
    await db_session.commit()
    return profile_id, job_id


@pytest.mark.anyio
async def test_refresh_matches_is_idempotent_and_read_only(client: AsyncClient, db_session) -> None:
    profile_id, job_id = await _seed_match_inputs(db_session)
    payload = {"profile_id": profile_id, "profile_version": 1, "job_ids": [job_id]}

    first = await client.post("/api/v1/matches/refresh", json=payload)
    second = await client.post("/api/v1/matches/refresh", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created"] == 1
    assert second.json()["created"] == 0
    assert second.json()["matches"][0]["id"] == first.json()["matches"][0]["id"]
    assert (await db_session.execute(select(Match))).scalars().all().__len__() == 1


@pytest.mark.anyio
async def test_refresh_all_scores_every_profile_and_is_idempotent(
    client: AsyncClient, db_session
) -> None:
    await _seed_match_inputs(db_session)

    first = await client.post("/api/v1/matches/refresh-all")
    second = await client.post("/api/v1/matches/refresh-all")

    assert first.status_code == 200
    body = first.json()
    assert body["profiles"] == 1
    assert body["jobs"] == 1
    assert body["created"] == 1
    assert body["per_profile"][0]["created"] == 1
    # Second pass creates nothing new — matches are idempotent by fingerprint.
    assert second.json()["created"] == 0
    assert (await db_session.execute(select(Match))).scalars().all().__len__() == 1


@pytest.mark.anyio
async def test_match_api_rejects_unknown_profile_version(client: AsyncClient, db_session) -> None:
    profile_id, job_id = await _seed_match_inputs(db_session)

    response = await client.post("/api/v1/matches/refresh", json={
        "profile_id": profile_id, "profile_version": 99, "job_ids": [job_id],
    })

    assert response.status_code == 404
    assert "version" in response.json()["detail"]


@pytest.mark.anyio
async def test_match_list_and_detail_are_read_only(client: AsyncClient, db_session) -> None:
    profile_id, job_id = await _seed_match_inputs(db_session)
    await client.post("/api/v1/matches/refresh", json={"profile_id": profile_id, "job_ids": [job_id]})

    listing = await client.get("/api/v1/matches", params={"profile_id": profile_id})
    match_id = listing.json()[0]["id"]
    detail = await client.get(f"/api/v1/matches/{match_id}")

    assert listing.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["profile_version"] == 1
    assert "application" not in detail.json()


@pytest.mark.anyio
async def test_changed_job_snapshot_creates_a_new_match_result(client: AsyncClient, db_session) -> None:
    profile_id, job_id = await _seed_match_inputs(db_session)
    payload = {"profile_id": profile_id, "profile_version": 1, "job_ids": [job_id]}
    first = await client.post("/api/v1/matches/refresh", json=payload)

    job = await db_session.get(Job, job_id)
    assert job is not None
    job.snapshot_hash = "hash-2"
    await db_session.commit()

    second = await client.post("/api/v1/matches/refresh", json=payload)

    assert first.json()["created"] == 1
    assert second.json()["created"] == 1
    assert second.json()["matches"][0]["input_fingerprint"] != first.json()["matches"][0]["input_fingerprint"]
