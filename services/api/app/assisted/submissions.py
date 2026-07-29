"""
Persistence for in-process mock ATS receipts.

Both the sandbox board endpoint and the assisted-run submit action funnel through
`record_submission`, so there is exactly one code path that can write a receipt
and exactly one place where the sandbox-only guard is enforced.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_ats import MockAtsSubmission

from .mock_ats import MockAtsError, confirmation_code, validate_payload


def build_idempotency_key(
    *, board_token: str, external_job_id: str, application_id: str, packet_hash: str | None
) -> str:
    return f"{board_token}:{external_job_id}:{application_id}:{packet_hash or 'no-packet'}"


async def record_submission(
    db: AsyncSession,
    *,
    board_token: str,
    external_job_id: str,
    application_id: str,
    payload: dict[str, str],
    browser_run_id: str | None = None,
    packet_hash: str | None = None,
) -> tuple[MockAtsSubmission, bool]:
    """
    Record one sandbox submission.

    Returns ``(receipt, created)``. Replaying the same packet against the same
    sandbox job returns the original receipt instead of writing a duplicate.
    """
    if not board_token.endswith("-mock"):
        raise MockAtsError(
            f"board {board_token!r} is not a mock sandbox board; refusing to record a submission"
        )
    clean_payload = validate_payload(payload)
    key = build_idempotency_key(
        board_token=board_token,
        external_job_id=external_job_id,
        application_id=application_id,
        packet_hash=packet_hash,
    )

    existing = await db.scalar(
        select(MockAtsSubmission).where(MockAtsSubmission.idempotency_key == key)
    )
    if existing is not None:
        return existing, False

    receipt = MockAtsSubmission(
        id=str(uuid.uuid4()),
        board_token=board_token,
        external_job_id=external_job_id,
        application_id=application_id,
        browser_run_id=browser_run_id,
        confirmation_code=confirmation_code(key),
        packet_hash=packet_hash,
        payload=dict(clean_payload),
        idempotency_key=key,
    )
    try:
        async with db.begin_nested():
            db.add(receipt)
            await db.flush()
    except IntegrityError:
        stored = await db.scalar(
            select(MockAtsSubmission).where(MockAtsSubmission.idempotency_key == key)
        )
        if stored is None:
            raise
        return stored, False
    return receipt, True
