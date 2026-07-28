from app.matching.engine import MatchConstraints, evaluate_match, fingerprint_inputs


def test_hard_eligibility_rejects_non_remote_job_with_reason() -> None:
    job = {
        "id": "job-1", "snapshot_hash": "job-hash", "title": "Python Engineer",
        "company": "Example", "location": "New York, NY", "is_remote": False,
        "employment_type": "full_time", "requirements": ["Python"],
        "nice_to_have": [], "technologies": ["Python"], "description": "Build APIs",
    }
    profile = {"id": "candidate-1", "version": 2, "skills": ["Python"],
               "summary": "Engineer", "work_experience": [], "education": [],
               "contact_info": {"location": "New York, NY"}}

    result = evaluate_match(job, profile, MatchConstraints(remote_only=True))

    assert result.eligible is False
    assert result.score == 0.0
    assert "Job is not remote" in result.reasons


def test_positive_match_has_deterministic_score_and_explanation() -> None:
    job = {
        "id": "job-2", "snapshot_hash": "job-hash", "title": "Senior Python Engineer",
        "company": "Example", "location": "Remote", "is_remote": True,
        "employment_type": "full_time", "requirements": ["Python", "FastAPI"],
        "nice_to_have": ["PostgreSQL"], "technologies": ["Python", "FastAPI"],
        "description": "Senior backend role",
    }
    profile = {"id": "candidate-1", "version": 1, "skills": ["Python", "FastAPI", "SQLAlchemy"],
               "summary": "Backend engineer", "work_experience": [{"title": "Python Engineer"}],
               "education": [{"degree": "Computer Science"}], "contact_info": {"location": "Remote"}}

    first = evaluate_match(job, profile, MatchConstraints())
    second = evaluate_match(job, profile, MatchConstraints())

    assert first.eligible is True
    assert first.score > 0
    assert first.model_dump() == second.model_dump()
    assert first.explanation["skills"]["matched"] == ["fastapi", "python"]
    assert first.explanation["title"]["overlap"] == ["engineer", "python"]


def test_empty_and_malformed_profile_data_is_safe() -> None:
    job = {
        "id": "job-3", "snapshot_hash": "job-hash", "title": "Engineer",
        "company": "Example", "location": None, "is_remote": True,
        "employment_type": None, "requirements": ["Python"], "nice_to_have": [],
        "technologies": [], "description": "Role",
    }
    result = evaluate_match(job, {"id": "candidate", "version": 1, "skills": "not-a-list"}, MatchConstraints())

    assert result.eligible is True
    assert result.score == 0.0
    assert result.explanation["skills"]["matched"] == []


def test_fingerprint_changes_when_job_or_profile_input_changes() -> None:
    base_job = {"id": "job", "snapshot_hash": "hash-a"}
    base_profile = {"id": "candidate", "version": 1, "skills": ["Python"]}

    original = fingerprint_inputs(base_job, base_profile, MatchConstraints())
    changed_job = fingerprint_inputs({**base_job, "snapshot_hash": "hash-b"}, base_profile, MatchConstraints())
    changed_profile = fingerprint_inputs(base_job, {**base_profile, "version": 2}, MatchConstraints())

    assert original != changed_job
    assert original != changed_profile
