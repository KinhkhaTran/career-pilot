"""
In-process mock ATS sandbox.

This module defines a fake application board that lives entirely inside the
CareerPilot API process and its own database fixture table. It exists so the
assisted-application journey can be exercised end to end without ever contacting
an employer.

SAFETY BOUNDARY
---------------
* Sandbox targets use the ``mock-ats://`` scheme. Nothing else is accepted.
* ``assert_mock_target`` rejects every http/https destination, so an assisted
  run can never be pointed at a real careers page.
* The sandbox has no login, no verification challenge, and no code-retrieval
  step, so there is nothing here for automation to bypass.
* Recording a sandbox receipt never advances the application state machine past
  ``stopped_before_submit``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

MOCK_ATS_SCHEME = "mock-ats"
MOCK_ATS_URL_PREFIX = f"{MOCK_ATS_SCHEME}://"

#: Human-facing label rendered anywhere a sandbox target is shown.
MOCK_ATS_LABEL = "MOCK ATS SANDBOX — not a real employer"

#: Fields the sandbox form accepts. Deliberately identical to the assisted-run
#: allowlist: non-sensitive, human-reviewed packet content only.
ALLOWED_MOCK_FIELDS = frozenset(
    {"full_name", "email", "phone", "linkedin", "resume", "cover_letter"}
)


class MockAtsError(ValueError):
    """Raised when a target or payload is not a valid sandbox interaction."""


@dataclass(frozen=True)
class MockFormField:
    name: str
    label: str
    selector: str
    kind: str
    required: bool


#: Ordered form definition. The order is the deterministic autofill order.
MOCK_ATS_FORM: tuple[MockFormField, ...] = (
    MockFormField("full_name", "Full name", "input[name='name']", "text", True),
    MockFormField("email", "Email", "input[name='email']", "email", True),
    MockFormField("phone", "Phone", "input[name='phone']", "tel", False),
    MockFormField("linkedin", "LinkedIn", "input[name='urls[LinkedIn]']", "url", False),
    MockFormField("resume", "Résumé", "textarea[name='resume_text']", "textarea", True),
    MockFormField("cover_letter", "Cover letter", "textarea[name='cover_letter']", "textarea", False),
)

_FIELDS_BY_NAME = {field.name: field for field in MOCK_ATS_FORM}


def board_token(source: str) -> str:
    """Return the sandbox board token that stands in for a real ATS source."""
    cleaned = (source or "generic").strip().lower().replace(" ", "-")
    return f"{cleaned}-mock"


def mock_ats_url(source: str, external_id: str) -> str:
    """Build the sandbox application URL for a stored job."""
    return f"{MOCK_ATS_URL_PREFIX}{board_token(source)}/{external_id}"


def is_mock_target(url: str) -> bool:
    return isinstance(url, str) and url.startswith(MOCK_ATS_URL_PREFIX)


def assert_mock_target(url: str) -> tuple[str, str]:
    """
    Validate a sandbox target and return ``(board_token, external_job_id)``.

    Any non-``mock-ats://`` URL — in particular any http/https employer URL — is
    rejected. This is the single choke point for sandbox-only assisted runs.
    """
    if not is_mock_target(url):
        raise MockAtsError(
            "assisted runs may only target the in-process mock ATS sandbox "
            f"({MOCK_ATS_URL_PREFIX}…); refusing real destination {url!r}"
        )
    parsed = urlparse(url)
    token = parsed.netloc
    external_job_id = parsed.path.lstrip("/")
    if not token or not external_job_id:
        raise MockAtsError(f"malformed mock ATS target {url!r}")
    return token, external_job_id


def form_definition(token: str) -> dict[str, Any]:
    """Public description of the sandbox form, used by the dashboard preview."""
    return {
        "board_token": token,
        "label": MOCK_ATS_LABEL,
        "is_mock": True,
        "fields": [
            {
                "name": field.name,
                "label": field.label,
                "selector": field.selector,
                "kind": field.kind,
                "required": field.required,
            }
            for field in MOCK_ATS_FORM
        ],
    }


def field_for(name: str) -> MockFormField:
    field = _FIELDS_BY_NAME.get(name)
    if field is None:
        raise MockAtsError(f"field is not part of the mock ATS form: {name!r}")
    return field


def validate_payload(payload: dict[str, str]) -> dict[str, str]:
    """Reject unknown or sensitive keys before anything is persisted."""
    unknown = sorted(set(payload) - ALLOWED_MOCK_FIELDS)
    if unknown:
        raise MockAtsError(f"fields are not accepted by the mock ATS form: {unknown}")
    missing = [
        field.name for field in MOCK_ATS_FORM if field.required and not payload.get(field.name)
    ]
    if missing:
        raise MockAtsError(f"mock ATS form is missing required fields: {missing}")
    return {name: str(value) for name, value in payload.items()}


def confirmation_code(idempotency_key: str) -> str:
    """Deterministic sandbox confirmation code, so replays are recognisable."""
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:10].upper()
    return f"MOCK-{digest}"
