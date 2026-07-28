# CareerPilot

CareerPilot is a clean-room, human-reviewed AI job discovery and assisted-application workspace.

> **Initial release boundary:** Always stops before final submission. No CAPTCHA solving, no identity-verification bypass, no job-site password storage, no inbox-code retrieval, no unattended submission.

## Phase 2 — Job Discovery

Phase 2 adds public read-only job discovery from Greenhouse, Lever, and Ashby.

| Feature | Status |
|---------|--------|
| Greenhouse public board adapter | ✅ |
| Lever public postings adapter | ✅ |
| Ashby public job board adapter | ✅ |
| Generic crawler boundary interface (Crawl4AI-compatible) | ✅ |
| Job normalization (HTML stripping, remote/tech detection) | ✅ |
| Deterministic SHA-256 snapshot deduplication | ✅ |
| Discovery run models + append-only event log | ✅ |
| `discover_jobs_task` ARQ worker task | ✅ |
| Discovery runs API (`GET /api/v1/discovery/runs`) | ✅ |
| Dashboard discovery runs page | ✅ |
| Mock ATS fixtures (`fixtures/mock-ats/`) | ✅ |

## Phase 1 — Foundation

This monorepo provides:

| Component | Path | Description |
|-----------|------|-------------|
| Dashboard | `apps/dashboard` | Next.js 14 (App Router) · TypeScript strict |
| API | `services/api` | FastAPI · SQLAlchemy async · Pydantic v2 |
| Worker | `services/worker` | ARQ · Greenhouse/Lever/Ashby adapters |
| Contracts | `packages/contracts` | Shared TypeScript types |
| UI | `packages/ui` | Accessible React primitives |
| DB | `db/` | Alembic migrations · Fake seed data |
| Infra | `infra/` | Docker Compose |
| Docs | `docs/` | Architecture · ADRs · Security |
| Fixtures | `fixtures/mock-ats/` | Deterministic ATS mock payloads |

## Quick start

```bash
# 1. Copy env and install all dependencies
cp .env.example .env
make setup

# 2. Start PostgreSQL + Redis
make docker-up

# 3. Run database migrations
make migrate

# 4. Load fake seed data
make seed

# 5. Start services (separate terminals)
make dev-api       # FastAPI → http://localhost:8000
make dev-dashboard # Next.js → http://localhost:3000
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Tests

```bash
make test                 # All tests
make test-state-machine   # State machine safety tests only
```

Key safety test: `services/api/tests/test_state_machine.py` proves that `SUBMITTED` is unreachable from any state when `INITIAL_SUBMISSION_MODE=stop_before_submit`.

## CI

```bash
make ci   # Full CI: lint · typecheck · test · docker-validate · secret-scan
```

GitHub Actions runs the same pipeline on every push/PR.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full architecture including Mermaid state machine and ER diagrams.

## Safety

The state machine in `services/api/app/state_machine/application.py` enforces:

```
DRAFT → MATCHED → PACKET_DRAFT → PACKET_READY → HUMAN_REVIEW → APPROVED → STOPPED_BEFORE_SUBMIT
```

`SUBMITTED` exists in the model for future compatibility but is unreachable in initial mode. A BFS graph test in CI verifies this invariant.

## Reference and licensing

Independently implemented. May learn product concepts from `job-application-automation`, `ApplyPilot`, and `Crawl4AI`, but does not copy source. ApplyPilot is AGPL-3.0-only; its code is not incorporated.

Never place real credentials in `.env.example`, seed data, logs, or commits.
