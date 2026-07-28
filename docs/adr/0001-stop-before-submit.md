# ADR-0001: Initial Release Always Stops Before Final Submission

**Status:** Accepted
**Date:** 2024-07-01
**Deciders:** CareerPilot project team

## Context

CareerPilot automates discovery, normalization, matching, packet preparation, and review of job applications. The central question for the initial release is whether to include final application submission to employer sites.

Employer-site submission introduces significant surface area: CAPTCHA handling, session management, form field mapping, identity verification, inbox-code retrieval, and error recovery. Each of these carries legal, ethical, and operational risk that is disproportionate to a first release.

There is also a correctness requirement: any submission must be bound to the exact candidate profile version, resume version, answer versions, job snapshot hash, and packet fingerprint that were reviewed and approved by the human. This binding mechanism is Phase 5 work.

## Decision

The initial release MUST NOT perform final application submission to any employer site.

The application state machine stops at `stopped_before_submit`, which is a terminal state in initial release mode (`INITIAL_SUBMISSION_MODE=stop_before_submit`). The service layer enforces this unconditionally: the transition from `approved` to `submitted` raises `SubmissionBlockedError` when the mode is `stop_before_submit`.

This is enforced at three layers:

1. **State machine** — `SubmissionBlockedError` is raised; the transition is not registered.
2. **CI prohibited-automation scan** — Patterns like `captcha_solve`, `bypass_verification`, `proxy_rotation`, `inbox_code_retrieval`, and `auto_submit` are banned from all source files.
3. **CI submission mode check** — `INITIAL_SUBMISSION_MODE=allow_submit` must not appear in non-test source.

A BFS reachability test proves that `SUBMITTED` is unreachable from `DRAFT` when the mode is `stop_before_submit`.

## Consequences

- No CAPTCHA solving, identity verification bypass, proxy rotation, or inbox code retrieval in any release without explicit Phase 5 design and authorization.
- Future releases that support submission require: explicit authorization tied to exact profile version, resume version, answer versions, job snapshot hash, packet fingerprint, and final browser-run state.
- CI includes `check-no-submit-bypass` (implemented as the `prohibited-automation-scan` and `secret-scan` jobs) that scan source for prohibited automation patterns.
- Tests prove `SUBMITTED` is unreachable from `DRAFT` under `stop_before_submit` mode via BFS graph traversal.

## Rejected Alternatives

- **"Opt-in submit per application"**: Rejected because the authorization requirements (fingerprint binding, multi-layer human confirmation gate) are Phase 5+ work and are not safe to ship as a minimal implementation.
- **"Always stop, but allow override via env var"**: Rejected because environment variable overrides can be set accidentally in deployment environments. A full feature-flag plus confirmation gate bound to a specific packet fingerprint is required. An env var alone provides no safety guarantee.
- **"Submit but log only"**: Rejected because any automated form submission to employer sites without a proper confirmation gate violates the safety boundary regardless of whether it is logged.
