from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff as make_unified_diff
from typing import Any


@dataclass(frozen=True)
class TailoredResume:
    text: str
    source_claims: list[str]
    added_claims: list[str]


def _claims(profile: dict[str, Any]) -> list[str]:
    claims: list[str] = []
    for experience in profile.get("work_experience") or []:
        if not isinstance(experience, dict):
            continue
        for claim in experience.get("achievements") or []:
            if isinstance(claim, str) and claim.strip():
                claims.append(claim.strip())
    return claims


def tailor_resume(profile: dict[str, Any], job: dict[str, Any]) -> TailoredResume:
    """Create a truthful plain-text résumé from profile facts only.

    Tailoring changes ordering and emphasis; it never invents a claim.
    """
    claims = _claims(profile)
    text_parts = [str(profile.get("summary") or "").strip()]
    text_parts.extend(claims)
    skills = [str(skill).strip() for skill in profile.get("skills") or [] if str(skill).strip()]
    if skills:
        text_parts.append("Skills: " + ", ".join(skills))
    text = "\n".join(part for part in text_parts if part)
    return TailoredResume(text=text, source_claims=claims, added_claims=[])


def unified_diff(original: str, tailored: str) -> str:
    return "".join(
        make_unified_diff(
            original.splitlines(True),
            tailored.splitlines(True),
            fromfile="original",
            tofile="tailored",
        )
    )
