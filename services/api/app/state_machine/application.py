"""
Application state machine.

Safety invariant: When initial_submission_mode == "stop_before_submit",
transitions to ApplicationStatus.SUBMITTED are unconditionally blocked.
The APPROVED state always flows to STOPPED_BEFORE_SUBMIT.

The SUBMITTED state is modelled for future compatibility but must be
unreachable in the initial release.
"""
from __future__ import annotations

from enum import Enum


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    MATCHED = "matched"
    PACKET_DRAFT = "packet_draft"
    PACKET_READY = "packet_ready"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    STOPPED_BEFORE_SUBMIT = "stopped_before_submit"
    SUBMITTED = "submitted"  # unreachable in initial release


# All possible transitions (full system graph)
TRANSITIONS: dict[ApplicationStatus, list[ApplicationStatus]] = {
    ApplicationStatus.DRAFT: [ApplicationStatus.MATCHED],
    ApplicationStatus.MATCHED: [ApplicationStatus.PACKET_DRAFT],
    ApplicationStatus.PACKET_DRAFT: [ApplicationStatus.PACKET_READY],
    ApplicationStatus.PACKET_READY: [ApplicationStatus.HUMAN_REVIEW],
    ApplicationStatus.HUMAN_REVIEW: [ApplicationStatus.APPROVED],
    ApplicationStatus.APPROVED: [
        ApplicationStatus.STOPPED_BEFORE_SUBMIT,
        ApplicationStatus.SUBMITTED,  # gated in initial release
    ],
    ApplicationStatus.STOPPED_BEFORE_SUBMIT: [],  # terminal in initial release
    ApplicationStatus.SUBMITTED: [],  # terminal
}

# The initial release is permanently stop-before-submit. A future release may
# add a separate, explicitly authorized confirmation transition, but no mode
# value can enable submission in this release.
INITIAL_MODE_BLOCKED: frozenset[ApplicationStatus] = frozenset({
    ApplicationStatus.SUBMITTED,
})


class StateMachineError(Exception):
    pass


class SubmissionBlockedError(StateMachineError):
    """Raised when initial mode prevents a transition to SUBMITTED."""
    pass


def can_transition(
    current: ApplicationStatus,
    target: ApplicationStatus,
    *,
    submission_mode: str,
) -> bool:
    if target not in TRANSITIONS.get(current, []):
        return False
    if target in INITIAL_MODE_BLOCKED:
        return False
    return True


def transition(
    current: ApplicationStatus,
    target: ApplicationStatus,
    *,
    submission_mode: str | None = None,
) -> ApplicationStatus:
    from app.config import settings
    effective_mode = (
        submission_mode
        if submission_mode is not None
        else settings.initial_submission_mode
    )

    if target not in TRANSITIONS.get(current, []):
        raise StateMachineError(
            f"Invalid transition: {current.value!r} → {target.value!r}. "
            f"Allowed from {current.value!r}: {[s.value for s in TRANSITIONS.get(current, [])]}"
        )

    if target in INITIAL_MODE_BLOCKED:
        raise SubmissionBlockedError(
            f"Transition to {target.value!r} is blocked: "
            f"INITIAL_SUBMISSION_MODE={effective_mode!r}. "
            "The initial release always stops before submission; a future release gate is required."
        )

    return target
