# ADR-0002: Immutable Append-Only Application Event Log

**Status:** Accepted
**Date:** 2024-07-01
**Deciders:** CareerPilot project team

## Context

Application state must be auditable and tamper-evident. When a human approves an application packet, that approval must be verifiable: which packet version was approved, by whom, at what time, and from which prior state. Mutable status fields with no history are insufficient for this requirement.

Additionally, the safety boundary (ADR-0001) requires that future authorization gates bind approval to an exact packet fingerprint. This binding is only meaningful when the approval history is trustworthy and cannot be silently overwritten.

## Decision

`ApplicationEvent` rows are immutable. The `application_events` table has no `updated_at` column and is only written via `INSERT`. No `UPDATE` or `DELETE` operations are permitted on this table in application code.

The current application status is stored in the `status` column on the `applications` table for fast lookup and JOIN performance. Every transition that mutates this column also appends an `ApplicationEvent` row within the same database transaction. The event records:

- `from_status` — the status before the transition
- `to_status` — the status after the transition
- `triggered_by` — `"system"` or `"human:<user-id>"`
- `note` — optional human-readable annotation
- `created_at` — set by the database; never set by the application

## Rationale

- The audit trail survives application bugs, task retries, and operator error because rows are never overwritten.
- Fingerprint comparison during future authorization gates is meaningful only when the event history is trustworthy.
- The full transition history enables replay and verification for debugging.
- A denormalized `status` column on `applications` keeps queries simple without sacrificing auditability.

## Consequences

- Application code must never issue `UPDATE application_events` or `DELETE FROM application_events`. This must be enforced by code review and, optionally, by a database-level row-level security rule in production.
- Replaying state from event history requires a sequential scan; the `status` column on `applications` avoids this for normal read paths.
- Future authorization gates (Phase 5) can verify the exact sequence of human approvals by reading `application_events` in chronological order.

## Rejected Alternatives

- **Event sourcing only (no status column on `applications`)**: Rejected as overly complex for Phase 1. Deriving current status by replaying all events on every read is expensive and unnecessary when the `status` column can serve as a fast lookup index. The hybrid approach (denormalized status + append-only event log) gives both performance and auditability.
- **Soft deletes with `deleted_at`**: Rejected because soft deletes still allow logical removal of event rows, which undermines the tamper-evident guarantee.
- **`updated_at` on `ApplicationEvent`**: Rejected. An immutable event has no meaningful update time. Adding `updated_at` would imply mutability where none is intended.
