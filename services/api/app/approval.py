"""Approval-token minting for the token-gated submission path (ADR 0008).

IMPORTANT: this MUST stay algorithmically identical to
``services/worker/app/browser_worker/approval.py`` — the API mints tokens and the
isolated browser worker verifies them, so both compute the canonical binding and
HMAC the same way. The binding covers the six immutable facts from requirement 12:
application_id, job_id, resume_version, answer_set_version, browser_run_id,
final_page_fingerprint.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ApprovalBinding:
    application_id: str
    job_id: str
    resume_version: int
    answer_set_version: int
    browser_run_id: str
    final_page_fingerprint: str

    def canonical(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()


def issue_token(token_id: str, binding: ApprovalBinding, *, secret: str) -> str:
    if not secret:
        raise ValueError("an approval signing secret is required")
    mac = hmac.new(
        secret.encode(),
        f"{token_id}.{binding.canonical()}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{token_id}.{mac}"
