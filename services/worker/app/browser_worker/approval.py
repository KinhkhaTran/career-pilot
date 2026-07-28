"""One-time approval token binding a submit click to an exact application state.

A token authorises exactly one Submit click. It is bound (via HMAC) to six
immutable facts (requirement 12):

    application_id, job_id, resume_version, answer_set_version,
    browser_run_id, final_page_fingerprint

If any of those differ at submit time — a re-tailored résumé, an edited answer,
a changed Review page — verification fails and the runner refuses to submit.
Tokens are single-use: a :class:`TokenStore` records consumption so the same
token can never drive a second submission.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Protocol


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


class ApprovalError(Exception):
    """Raised when a token is missing, malformed, mismatched, or already used."""


class TokenStore(Protocol):
    async def consume(self, token_id: str, binding_digest: str) -> bool:
        """Atomically mark ``token_id`` used. Return True only on first use."""
        ...


class InMemoryTokenStore:
    """A single-process token store (used by tests and single-run flows)."""

    def __init__(self) -> None:
        self._used: dict[str, str] = {}

    async def consume(self, token_id: str, binding_digest: str) -> bool:
        if token_id in self._used:
            return False
        self._used[token_id] = binding_digest
        return True


def issue_token(token_id: str, binding: ApprovalBinding, *, secret: str) -> str:
    """Mint an approval token string of the form ``<token_id>.<hmac hex>``.

    ``token_id`` is a caller-supplied unique id (e.g. a UUID) so the token can be
    tracked and revoked. The signature covers both the id and the binding.
    """
    if not secret:
        raise ApprovalError("an approval signing secret is required")
    mac = hmac.new(
        secret.encode(),
        f"{token_id}.{binding.canonical()}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{token_id}.{mac}"


def _verify_signature(token: str, binding: ApprovalBinding, *, secret: str) -> str:
    try:
        token_id, provided = token.split(".", 1)
    except ValueError as exc:  # noqa: TRY003
        raise ApprovalError("malformed approval token") from exc
    expected = hmac.new(
        secret.encode(),
        f"{token_id}.{binding.canonical()}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, provided):
        raise ApprovalError(
            "approval token does not match this application/résumé/answers/run/page"
        )
    return token_id


async def verify_and_consume(
    token: str | None,
    binding: ApprovalBinding,
    *,
    secret: str,
    store: TokenStore,
) -> str:
    """Verify a token against ``binding`` and consume it. Returns the token id.

    Raises :class:`ApprovalError` if the token is absent, forged, bound to a
    different state, or has already been used.
    """
    if not token:
        raise ApprovalError("no approval token supplied; submission is not authorised")
    token_id = _verify_signature(token, binding, secret=secret)
    if not await store.consume(token_id, binding.digest()):
        raise ApprovalError("approval token has already been used; submission blocked")
    return token_id
