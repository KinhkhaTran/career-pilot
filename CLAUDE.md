# CareerPilot project instructions

Read `BUILD_SPEC.md` and `docs/architecture.md` before implementation.

## Engineering

- TypeScript strict mode for dashboard and shared contracts.
- Python typing, Pydantic validation, Ruff, and mypy for services.
- Prefer small modular adapters, explicit state machines, idempotency keys, bounded retries, and append-only audit events.
- Public job discovery and browser workers are isolated from the dashboard/API.
- Do not copy code from ApplyPilot or other reference repositories. Reimplement concepts clean-room and preserve license attribution only where dependencies require it.

## Required verification

Run tests, typechecks, builds, Docker Compose config validation, secret scans, and prohibited-automation scans before claiming a phase complete.
