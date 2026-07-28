# ADR 0008: Token-Gated Supervised Submission (Workday)

**Status:** Accepted — supersedes the "all releases stop before submit" reading of ADR 0001

## Context

ADR 0001 established that the initial release always stops before final
submission. BUILD_SPEC anticipated a later release that "may require explicit
authorization tied to the exact résumé, answers, packet fingerprint, job
snapshot, and final browser state." This ADR introduces that explicitly
authorized path for the Workday ATS, behind a supervised human-in-the-loop
runner.

## Decision

Submission remains **off by default**. The generic state-machine `transition()`
still treats `SUBMITTED` as unconditionally blocked under every
`INITIAL_SUBMISSION_MODE` value — the existing safety tests are unchanged. A
submit becomes possible only through a **separate, explicit** path:

1. `INITIAL_SUBMISSION_MODE=allow_submit` (opt-in), **and**
2. a verified, single-use **approval token** bound via HMAC to six immutable
   facts: `application_id`, `job_id`, `resume_version`, `answer_set_version`,
   `browser_run_id`, and the `final_page_fingerprint` (SHA-256 of the reviewed
   Review page).

The only producer of `SUBMITTED` is `authorize_submission()`, which requires
both conditions. Configuration alone can never submit — an authorization object
representing a verified token is mandatory.

The supervised runner (`SupervisedApplicationRunner` + `WorkdayAdapter`):

- Runs only headful, against a persistent local profile the human logs into by
  hand. Headless is rejected.
- Fills only human-approved, non-sensitive fields; **pauses** on any missing
  answer, sub-threshold confidence, legally sensitive/EEO question, attestation,
  CAPTCHA, MFA, or identity-verification wall — it never solves or bypasses them.
- Stops at the employer's Review page and reports full state to the dashboard.
- Clicks the employer's existing Submit control **exactly once**, only after
  `verify_and_consume` accepts the token for this exact state.
- Detects the confirmation page, stores evidence, and is idempotent across
  resumes via a single-use token, a `submitted` guard, and confirmation
  detection — the same application cannot be submitted twice.

## Safety consequences

- Default behaviour is identical to ADR 0001/0007: stop before submit.
- No CAPTCHA solving, MFA/inbox-code retrieval, proxy rotation, automation
  concealment, or access-control bypass exists anywhere in the runner or
  launcher; these are detected and handed to a human.
- Enabling submission requires a deliberate config change **and** a per-run,
  fingerprint-bound, single-use token minted after human review. Any change to
  résumé, answers, or the Review page invalidates the token.
- The adapter is proven against a local mock Workday fixture
  (`fixtures/mock-ats/workday/` + the in-memory simulator) and its test suite
  before any real employer site is used.
