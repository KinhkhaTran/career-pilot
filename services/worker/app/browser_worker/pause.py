"""Pause conditions for the supervised application runner.

The runner never attempts to defeat, solve, or work around any of these
conditions. When one is detected it stops and surfaces the reason to a human,
who completes the step in the visible browser before the run is resumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import Enum
from typing import Any


class PauseReason(str, Enum):
    """Why a supervised run halted and handed control back to the human."""

    NOT_AT_APPLICATION_FORM = "not_at_application_form"
    UNSUPPORTED_ATS = "unsupported_ats"
    MISSING_ANSWER = "missing_answer"
    LOW_CONFIDENCE = "low_confidence"
    LEGALLY_SENSITIVE = "legally_sensitive"
    ATTESTATION = "attestation"
    CAPTCHA = "captcha"
    MFA = "mfa"
    IDENTITY_VERIFICATION = "identity_verification"
    LOGIN_REQUIRED = "login_required"
    VALIDATION_ERROR = "validation_error"
    STOPPED_AT_REVIEW = "stopped_at_review"


# Reasons that represent a legitimate, expected end-of-run handoff rather than a
# defect. The runner treats these as "paused" (awaiting human action) not "failed".
HUMAN_HANDOFF_REASONS: frozenset[PauseReason] = frozenset(
    {
        PauseReason.MISSING_ANSWER,
        PauseReason.LOW_CONFIDENCE,
        PauseReason.LEGALLY_SENSITIVE,
        PauseReason.ATTESTATION,
        PauseReason.CAPTCHA,
        PauseReason.MFA,
        PauseReason.IDENTITY_VERIFICATION,
        PauseReason.LOGIN_REQUIRED,
        PauseReason.STOPPED_AT_REVIEW,
    }
)


@dataclass(frozen=True)
class PauseSignal:
    """A single reason the run must hand control back to the human."""

    reason: PauseReason
    message: str
    field: str | None = None
    detail: dict[str, Any] = dc_field(default_factory=dict)

    def as_event(self) -> dict[str, Any]:
        return {
            "type": "paused",
            "reason": self.reason.value,
            "message": self.message,
            "field": self.field,
            **({"detail": self.detail} if self.detail else {}),
        }


class RunPaused(Exception):
    """Raised internally to unwind the step loop when a pause is required."""

    def __init__(self, signal: PauseSignal) -> None:
        super().__init__(signal.message)
        self.signal = signal
