# CareerPilot project instructions

Read `BUILD_SPEC.md` and `docs/architecture.md` before implementation.

## Non-negotiable safety boundary

- The initial release must always stop before final application submission.
- Employer-site automation is future work and must remain behind explicit feature flags and human approval gates.
- Any future confirmation workflow must bind approval to the exact profile version, résumé version, answer versions, job snapshot, packet fingerprint, and browser-run state.
- Never store job-site passwords in the database. Keep secrets out of source, logs, fixtures, and client bundles.
- Use fake seed data only.

## Engineering

- TypeScript strict mode for dashboard and shared contracts.
- Python typing, Pydantic validation, Ruff, and mypy for services.
- Prefer small modular adapters, explicit state machines, idempotency keys, bounded retries, and append-only audit events.
- Public job discovery and browser workers are isolated from the dashboard/API.
- Do not copy code from ApplyPilot or other reference repositories. Reimplement concepts clean-room and preserve license attribution only where dependencies require it.

## Required verification

Run tests, typechecks, builds, Docker Compose config validation, secret scans, and prohibited-automation scans before claiming a phase complete.
