from __future__ import annotations


def validate_answer(answer: str) -> str:
    value = answer.strip()
    if not value:
        raise ValueError("answer must not be empty")
    return value
