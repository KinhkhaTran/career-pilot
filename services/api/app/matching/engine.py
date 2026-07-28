from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, Field

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[+#.-][a-z0-9]+)*")
_STOPWORDS = {"and", "or", "the", "a", "an", "of", "to", "in", "for", "with", "on", "at"}


class MatchConstraints(BaseModel):
    """User-configurable hard eligibility constraints."""

    remote_only: bool = False
    allowed_locations: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    eligible: bool
    score: float
    reasons: list[str]
    explanation: dict[str, Any]


def _tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {token for token in _TOKEN_RE.findall(value.lower()) if token not in _STOPWORDS}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _nested_strings(value: Any, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if isinstance(item, dict):
            for key in keys:
                text = item.get(key)
                if isinstance(text, str):
                    output.append(text)
    return output


def _overlap(left: set[str], right: set[str]) -> list[str]:
    return sorted(left & right)


def _location_allowed(job: dict[str, Any], allowed: list[str]) -> bool:
    if not allowed:
        return True
    location = job.get("location")
    if not isinstance(location, str):
        return False
    location_tokens = _tokens(location)
    return any(_tokens(item) <= location_tokens for item in allowed if isinstance(item, str) and _tokens(item))


def evaluate_match(
    job: dict[str, Any], profile: dict[str, Any], constraints: MatchConstraints | None = None
) -> MatchResult:
    """Evaluate a normalized job against a profile using deterministic local scoring."""
    constraints = constraints or MatchConstraints()
    reasons: list[str] = []
    if constraints.remote_only and job.get("is_remote") is not True:
        reasons.append("Job is not remote")
    if not _location_allowed(job, constraints.allowed_locations):
        reasons.append("Job location is outside the allowed locations")
    employment_type = job.get("employment_type")
    if constraints.employment_types and (
        not isinstance(employment_type, str)
        or employment_type.lower() not in {item.lower() for item in constraints.employment_types}
    ):
        reasons.append("Employment type is not allowed")

    job_skill_text = _strings(job.get("requirements")) + _strings(job.get("technologies"))
    job_skill_tokens = set().union(*(_tokens(item) for item in job_skill_text)) if job_skill_text else set()
    profile_skill_tokens = set().union(*(_tokens(item) for item in _strings(profile.get("skills"))))
    matched_skills = _overlap(job_skill_tokens, profile_skill_tokens)
    skill_ratio = len(matched_skills) / len(job_skill_tokens) if job_skill_tokens else 0.0

    title_tokens = _tokens(job.get("title"))
    experience_titles = _nested_strings(profile.get("work_experience"), ("title", "description"))
    experience_tokens = set().union(*(_tokens(item) for item in experience_titles)) if experience_titles else set()
    title_overlap = _overlap(title_tokens, profile_skill_tokens)
    title_ratio = len(title_overlap) / len(title_tokens) if title_tokens else 0.0

    requirement_tokens = set().union(*(_tokens(item) for item in _strings(job.get("requirements"))))
    education_text = _nested_strings(profile.get("education"), ("degree", "field_of_study", "field"))
    education_tokens = set().union(*(_tokens(item) for item in education_text)) if education_text else set()
    education_overlap = _overlap(requirement_tokens, education_tokens)
    education_ratio = min(1.0, len(education_overlap) / max(1, len(requirement_tokens)))

    experience_overlap = _overlap(title_tokens, experience_tokens)
    experience_ratio = min(1.0, len(experience_overlap) / max(1, len(title_tokens)))
    score = round((skill_ratio * 0.5 + title_ratio * 0.2 + experience_ratio * 0.2 + education_ratio * 0.1) * 100, 2)
    eligible = not reasons
    if not eligible:
        score = 0.0

    return MatchResult(
        eligible=eligible,
        score=score,
        reasons=reasons,
        explanation={
            "skills": {"matched": matched_skills, "required": sorted(job_skill_tokens), "ratio": round(skill_ratio, 4)},
            "title": {"overlap": title_overlap, "job_tokens": sorted(title_tokens), "ratio": round(title_ratio, 4)},
            "experience": {"overlap": experience_overlap, "ratio": round(experience_ratio, 4)},
            "education": {"matched": education_overlap, "ratio": round(education_ratio, 4)},
            "weights": {"skills": 0.5, "title": 0.2, "experience": 0.2, "education": 0.1},
        },
    )


def fingerprint_inputs(
    job: dict[str, Any], profile: dict[str, Any], constraints: MatchConstraints
) -> str:
    payload = {"job": job, "profile": profile, "constraints": constraints.model_dump(mode="json")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
