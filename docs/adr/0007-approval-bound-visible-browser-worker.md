# ADR 0007: Approval-Bound Visible Browser Worker

**Status:** Accepted

## Decision

Phase 5 exposes a narrow browser-worker boundary backed by a Playwright-compatible page protocol and clean-room ATS form adapters. It is usable with deterministic fake page objects and does not require Playwright or live employer sites in tests.

A run requires an application in `approved`, exact equality between the request and stored packet fingerprint, and exact immutable profile/job inputs. Only explicitly allowlisted, non-sensitive fields from the approved packet may be filled. The worker captures screenshots and append-only steps/events, runs headful (`headless=False`), and records `stopped_before_submit`.

## Safety consequences

There is no submit method in the page protocol or adapter interface. Credentials, passwords, CAPTCHA/inbox/identity-verification workflows, proxy rotation, and unattended employer writes are intentionally absent. The API queues a run for a separately supervised worker; it cannot transition an application to `submitted`.
