"""
Deterministic, pausable autofill runner for the mock ATS sandbox.

The runner is a pure state machine over a persisted step plan. It performs no
network access and drives no browser: it fills an in-memory model of the sandbox
form so the dashboard can render every field as it is written.

The real browser boundary stays in the isolated worker service
(``services/worker/app/browser_worker``). Neither runner has a submit action —
both terminate at ``stopped_before_submit``.
"""

from __future__ import annotations

from typing import Any

from .mock_ats import MOCK_ATS_FORM, MOCK_ATS_LABEL, assert_mock_target, field_for

#: Terminal step of every plan. There is no step after it, and no step type that
#: presses an employer's submit control.
TERMINAL_ACTION = "stopped_before_submit"

RunStatus = str

QUEUED = "queued"
RUNNING = "running"
PAUSED = "paused"
STOPPED_BEFORE_SUBMIT = "stopped_before_submit"


class RunnerError(ValueError):
    """Raised when a plan or a run transition is invalid."""


def build_plan(approved_fields: dict[str, str], target_url: str) -> list[dict[str, Any]]:
    """
    Build the ordered step plan for a sandbox autofill.

    The plan is derived only from the approved packet fields and the sandbox form
    order, so the same approved packet always produces the same plan.
    """
    board, external_job_id = assert_mock_target(target_url)
    plan: list[dict[str, Any]] = [
        {
            "action": "open_mock_form",
            "detail": {
                "url": target_url,
                "board_token": board,
                "external_job_id": external_job_id,
                "target_kind": "mock_ats",
                "label": MOCK_ATS_LABEL,
            },
        }
    ]
    for form_field in MOCK_ATS_FORM:
        if form_field.name not in approved_fields:
            continue
        plan.append(
            {
                "action": "fill",
                "detail": {
                    "field": form_field.name,
                    "label": form_field.label,
                    "selector": form_field.selector,
                    "target_kind": "mock_ats",
                },
            }
        )
    unsupported = sorted(set(approved_fields) - {f.name for f in MOCK_ATS_FORM})
    if unsupported:
        raise RunnerError(f"approved fields are not supported by the mock form: {unsupported}")
    plan.append(
        {
            "action": "review_filled_form",
            "detail": {"target_kind": "mock_ats", "label": MOCK_ATS_LABEL},
        }
    )
    plan.append(
        {
            "action": TERMINAL_ACTION,
            "detail": {
                "reason": "initial_release_safety_boundary",
                "target_kind": "mock_ats",
            },
        }
    )
    return plan


def _preview(value: str) -> str:
    """Short, non-secret preview of a filled value for the audit log."""
    collapsed = " ".join(str(value).split())
    return collapsed if len(collapsed) <= 60 else f"{collapsed[:57]}…"


def execute_step(
    step: dict[str, Any], approved_fields: dict[str, str], form_state: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """
    Execute one planned step against the in-memory sandbox form.

    Returns ``(step_record, event_record, next_form_state)``. The step record is
    what gets appended to ``browser_run_steps``; the event record is appended to
    ``browser_run_events``. Neither this function nor its callers can submit.
    """
    action = str(step.get("action", ""))
    detail = dict(step.get("detail") or {})
    state = dict(form_state)

    if action == "open_mock_form":
        event = {"event_type": "mock_form_opened", "detail": detail}
    elif action == "fill":
        name = str(detail.get("field", ""))
        form_field = field_for(name)
        if name not in approved_fields:
            raise RunnerError(f"field {name!r} is not in the approved packet")
        state[name] = approved_fields[name]
        detail = {**detail, "value_preview": _preview(approved_fields[name])}
        event = {
            "event_type": "field_filled",
            "detail": {
                "field": name,
                "label": form_field.label,
                "value_preview": detail["value_preview"],
            },
        }
    elif action == "review_filled_form":
        detail = {**detail, "filled_fields": sorted(state)}
        event = {"event_type": "awaiting_human_review", "detail": detail}
    elif action == TERMINAL_ACTION:
        event = {"event_type": TERMINAL_ACTION, "detail": detail}
    else:
        raise RunnerError(f"unknown planned action: {action!r}")

    return {"action": action, "detail": detail}, event, state


def next_status(cursor: int, plan_length: int) -> RunStatus:
    """Status implied by a cursor position after advancing."""
    if cursor >= plan_length:
        return STOPPED_BEFORE_SUBMIT
    return RUNNING


def assert_advanceable(status: RunStatus) -> None:
    if status == PAUSED:
        raise RunnerError("run is paused; resume it before advancing")
    if status == STOPPED_BEFORE_SUBMIT:
        raise RunnerError("run already stopped before submit; there are no further steps")
    if status not in (QUEUED, RUNNING):
        raise RunnerError(f"run cannot be advanced from status {status!r}")


def assert_pausable(status: RunStatus) -> None:
    if status not in (QUEUED, RUNNING):
        raise RunnerError(f"only a queued or running assisted run can be paused (got {status!r})")


def assert_resumable(status: RunStatus) -> None:
    if status != PAUSED:
        raise RunnerError(f"only a paused assisted run can be resumed (got {status!r})")
