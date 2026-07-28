from __future__ import annotations

import pytest

from app.browser_worker import (
    ApprovalBinding,
    ApprovalError,
    InMemoryTokenStore,
    issue_token,
    verify_and_consume,
)

SECRET = "test-approval-secret"


def binding(**overrides: object) -> ApprovalBinding:
    values: dict[str, object] = {
        "application_id": "app-1",
        "job_id": "job-1",
        "resume_version": 3,
        "answer_set_version": 2,
        "browser_run_id": "run-1",
        "final_page_fingerprint": "fp-abc",
    }
    values.update(overrides)
    return ApprovalBinding(**values)  # type: ignore[arg-type]


async def test_valid_token_verifies_and_consumes_once() -> None:
    store = InMemoryTokenStore()
    b = binding()
    token = issue_token("tok-1", b, secret=SECRET)

    token_id = await verify_and_consume(token, b, secret=SECRET, store=store)
    assert token_id == "tok-1"

    # Single-use: the same token cannot drive a second submission.
    with pytest.raises(ApprovalError, match="already been used"):
        await verify_and_consume(token, b, secret=SECRET, store=store)


async def test_token_is_rejected_when_any_binding_field_changes() -> None:
    store = InMemoryTokenStore()
    token = issue_token("tok-1", binding(), secret=SECRET)
    for changed in (
        {"resume_version": 4},
        {"answer_set_version": 99},
        {"final_page_fingerprint": "fp-changed"},
        {"browser_run_id": "run-2"},
        {"application_id": "app-2"},
        {"job_id": "job-2"},
    ):
        with pytest.raises(ApprovalError, match="does not match"):
            await verify_and_consume(token, binding(**changed), secret=SECRET, store=store)


def test_token_algorithm_parity_vector() -> None:
    """Pin the HMAC to a fixed vector shared with the API's minter (anti-drift).

    The identical assertion lives in services/api/tests/test_approval_token_api.py.
    If either service changes the canonical binding or HMAC, this vector breaks.
    """
    b = ApprovalBinding(
        application_id="app-1",
        job_id="job-1",
        resume_version=3,
        answer_set_version=2,
        browser_run_id="run-1",
        final_page_fingerprint="fp-abc",
    )
    token = issue_token("tok-1", b, secret="parity-secret")
    assert token == "tok-1.490160f48976a44685a6410024393b7053a268e92614fc66c8fdbac949c4bb8b"


async def test_missing_and_forged_tokens_are_rejected() -> None:
    store = InMemoryTokenStore()
    b = binding()
    with pytest.raises(ApprovalError, match="not authorised"):
        await verify_and_consume(None, b, secret=SECRET, store=store)
    with pytest.raises(ApprovalError, match="does not match"):
        await verify_and_consume("tok-1.deadbeef", b, secret=SECRET, store=store)
    # Signed with the wrong secret.
    wrong = issue_token("tok-1", b, secret="other-secret")
    with pytest.raises(ApprovalError, match="does not match"):
        await verify_and_consume(wrong, b, secret=SECRET, store=store)
