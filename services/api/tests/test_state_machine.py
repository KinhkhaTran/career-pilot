from __future__ import annotations

from collections import deque

import pytest

from app.state_machine.application import (
    INITIAL_MODE_BLOCKED,
    TRANSITIONS,
    ApplicationStatus,
    StateMachineError,
    SubmissionAuthorization,
    SubmissionBlockedError,
    SubmissionNotAuthorizedError,
    authorize_submission,
    can_transition,
    transition,
)


def _authorization() -> SubmissionAuthorization:
    return SubmissionAuthorization(
        application_id="app-1",
        browser_run_id="run-1",
        token_id="tok-1",
        binding_digest="digest-abc",
        final_page_fingerprint="fp-abc",
    )


class TestExplicitSubmissionGate:
    """The token-bound gate is the ONLY producer of SUBMITTED (requirement 12-13)."""

    def test_generic_transition_still_blocks_submitted_under_any_mode(self) -> None:
        for mode in ("stop_before_submit", "allow_submit"):
            with pytest.raises(SubmissionBlockedError):
                transition(
                    ApplicationStatus.APPROVED,
                    ApplicationStatus.SUBMITTED,
                    submission_mode=mode,
                )

    def test_authorize_requires_allow_submit_mode(self) -> None:
        with pytest.raises(SubmissionBlockedError):
            authorize_submission(
                ApplicationStatus.APPROVED,
                authorization=_authorization(),
                submission_mode="stop_before_submit",
            )

    def test_authorize_requires_a_verified_token(self) -> None:
        with pytest.raises(SubmissionNotAuthorizedError):
            authorize_submission(
                ApplicationStatus.APPROVED,
                authorization=None,
                submission_mode="allow_submit",
            )

    def test_authorize_only_from_approved(self) -> None:
        with pytest.raises(StateMachineError):
            authorize_submission(
                ApplicationStatus.HUMAN_REVIEW,
                authorization=_authorization(),
                submission_mode="allow_submit",
            )

    def test_authorize_succeeds_with_mode_and_token(self) -> None:
        result = authorize_submission(
            ApplicationStatus.APPROVED,
            authorization=_authorization(),
            submission_mode="allow_submit",
        )
        assert result is ApplicationStatus.SUBMITTED


class TestStopBeforeSubmitSafety:
    """Proves the initial release cannot reach SUBMITTED state."""

    def test_submitted_is_in_blocked_set(self) -> None:
        assert ApplicationStatus.SUBMITTED in INITIAL_MODE_BLOCKED

    def test_approved_to_submitted_blocked_in_initial_mode(self) -> None:
        with pytest.raises(SubmissionBlockedError):
            transition(
                ApplicationStatus.APPROVED,
                ApplicationStatus.SUBMITTED,
                submission_mode="stop_before_submit",
            )

    def test_approved_to_stopped_before_submit_allowed(self) -> None:
        result = transition(
            ApplicationStatus.APPROVED,
            ApplicationStatus.STOPPED_BEFORE_SUBMIT,
            submission_mode="stop_before_submit",
        )
        assert result == ApplicationStatus.STOPPED_BEFORE_SUBMIT

    def test_stopped_before_submit_is_terminal(self) -> None:
        """No transitions out of STOPPED_BEFORE_SUBMIT."""
        assert TRANSITIONS[ApplicationStatus.STOPPED_BEFORE_SUBMIT] == []
        with pytest.raises(StateMachineError):
            transition(
                ApplicationStatus.STOPPED_BEFORE_SUBMIT,
                ApplicationStatus.SUBMITTED,
                submission_mode="stop_before_submit",
            )

    def test_can_transition_returns_false_for_blocked(self) -> None:
        assert (
            can_transition(
                ApplicationStatus.APPROVED,
                ApplicationStatus.SUBMITTED,
                submission_mode="stop_before_submit",
            )
            is False
        )

    def test_can_transition_returns_true_for_allowed(self) -> None:
        assert (
            can_transition(
                ApplicationStatus.APPROVED,
                ApplicationStatus.STOPPED_BEFORE_SUBMIT,
                submission_mode="stop_before_submit",
            )
            is True
        )

    def test_every_path_from_draft_blocked_before_submit(self) -> None:
        """BFS: all reachable states from DRAFT cannot reach SUBMITTED."""
        reachable: set[ApplicationStatus] = set()
        queue: deque[ApplicationStatus] = deque([ApplicationStatus.DRAFT])
        while queue:
            state = queue.popleft()
            if state in reachable:
                continue
            reachable.add(state)
            for next_state in TRANSITIONS.get(state, []):
                if can_transition(state, next_state, submission_mode="stop_before_submit"):
                    queue.append(next_state)
        assert ApplicationStatus.SUBMITTED not in reachable, (
            "SUBMITTED state is reachable from DRAFT in stop_before_submit mode — SAFETY VIOLATION"
        )

    def test_blocked_set_is_non_empty(self) -> None:
        """Ensure the blocked set is not accidentally emptied."""
        assert len(INITIAL_MODE_BLOCKED) >= 1

    def test_submitted_transition_raises_submission_blocked_not_generic(self) -> None:
        """SubmissionBlockedError is a subclass of StateMachineError but is distinct."""
        exc = None
        try:
            transition(
                ApplicationStatus.APPROVED,
                ApplicationStatus.SUBMITTED,
                submission_mode="stop_before_submit",
            )
        except SubmissionBlockedError as e:
            exc = e
        assert exc is not None
        assert isinstance(exc, SubmissionBlockedError)
        assert isinstance(exc, StateMachineError)
        assert "stop_before_submit" in str(exc)

    def test_submission_mode_cannot_enable_submission_in_initial_release(self) -> None:
        """No configuration value can bypass the initial release boundary."""
        with pytest.raises(SubmissionBlockedError):
            transition(
                ApplicationStatus.APPROVED,
                ApplicationStatus.SUBMITTED,
                submission_mode="allow_submit",
            )


class TestHappyPath:
    def test_full_path_to_stopped_before_submit(self) -> None:
        status = ApplicationStatus.DRAFT
        path = [
            ApplicationStatus.MATCHED,
            ApplicationStatus.PACKET_DRAFT,
            ApplicationStatus.PACKET_READY,
            ApplicationStatus.HUMAN_REVIEW,
            ApplicationStatus.APPROVED,
            ApplicationStatus.STOPPED_BEFORE_SUBMIT,
        ]
        for target in path:
            status = transition(status, target, submission_mode="stop_before_submit")
        assert status == ApplicationStatus.STOPPED_BEFORE_SUBMIT

    def test_each_sequential_transition_returns_target(self) -> None:
        pairs = [
            (ApplicationStatus.DRAFT, ApplicationStatus.MATCHED),
            (ApplicationStatus.MATCHED, ApplicationStatus.PACKET_DRAFT),
            (ApplicationStatus.PACKET_DRAFT, ApplicationStatus.PACKET_READY),
            (ApplicationStatus.PACKET_READY, ApplicationStatus.HUMAN_REVIEW),
            (ApplicationStatus.HUMAN_REVIEW, ApplicationStatus.APPROVED),
            (ApplicationStatus.APPROVED, ApplicationStatus.STOPPED_BEFORE_SUBMIT),
        ]
        for current, target in pairs:
            assert transition(current, target, submission_mode="stop_before_submit") == target


class TestInvalidTransitions:
    def test_draft_cannot_skip_to_approved(self) -> None:
        with pytest.raises(StateMachineError):
            transition(
                ApplicationStatus.DRAFT,
                ApplicationStatus.APPROVED,
                submission_mode="stop_before_submit",
            )

    def test_draft_cannot_go_to_submitted(self) -> None:
        with pytest.raises(StateMachineError):
            transition(
                ApplicationStatus.DRAFT,
                ApplicationStatus.SUBMITTED,
                submission_mode="stop_before_submit",
            )

    def test_terminal_state_has_no_transitions(self) -> None:
        with pytest.raises(StateMachineError):
            transition(
                ApplicationStatus.STOPPED_BEFORE_SUBMIT,
                ApplicationStatus.DRAFT,
                submission_mode="stop_before_submit",
            )

    def test_backwards_transition_raises(self) -> None:
        with pytest.raises(StateMachineError):
            transition(
                ApplicationStatus.PACKET_READY,
                ApplicationStatus.DRAFT,
                submission_mode="stop_before_submit",
            )

    def test_same_state_transition_raises(self) -> None:
        with pytest.raises(StateMachineError):
            transition(
                ApplicationStatus.DRAFT,
                ApplicationStatus.DRAFT,
                submission_mode="stop_before_submit",
            )

    def test_error_message_contains_allowed_transitions(self) -> None:
        with pytest.raises(StateMachineError) as exc_info:
            transition(
                ApplicationStatus.DRAFT,
                ApplicationStatus.APPROVED,
                submission_mode="stop_before_submit",
            )
        assert "matched" in str(exc_info.value)
