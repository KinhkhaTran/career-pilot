# CareerPilot

CareerPilot is a clean-room, human-reviewed AI job discovery and assisted-application workspace.

> **Initial release boundary:** Always stops before final submission. No CAPTCHA solving, no identity-verification bypass, no job-site password storage, no inbox-code retrieval, no unattended submission.

## Phase 5 — Assisted application

Phase 5 provides an approval-bound browser-worker boundary, not employer automation. A run can be started only for an `approved` application with an exact packet fingerprint and immutable profile/job inputs. The worker uses a Playwright-compatible page interface in visible/headful mode, fills only explicitly allowlisted packet fields, captures screenshots and append-only steps/events, and terminates in `stopped_before_submit`. It has no submit action, credentials, CAPTCHA, inbox-code, identity-verification, or proxy facilities. Start/read endpoints are `POST/GET /api/v1/applications/{id}/browser-runs`; deterministic Greenhouse-like mock adapters and fake pages keep tests offline.

| Feature | Status |
|---------|--------|
| Approval and packet/input fingerprint binding | ✅ |
| Visible Playwright-compatible worker boundary | ✅ |
| Allowlisted non-sensitive field filling | ✅ |
| Screenshot, step, and event audit persistence | ✅ |
| Stop-before-submit state transition | ✅ |
| Dashboard run status and audit view | ✅ |
| Employer writes or final submission | 🚫 permanently blocked in initial release |

## Phase 4 — Application materials

Phase 4 adds a complete, review-first materials vertical slice:

| Feature | Status |
|---------|--------|
| Truthful résumé tailoring from profile claims only | ✅ |
| Versioned material storage with unified diffs | ✅ |
| Deterministic packet fingerprints bound to profile, materials, answers, and job snapshot | ✅ |
| Reusable, versioned answer library | ✅ |
| Human review gate before approval | ✅ |
| Dashboard material and diff view | ✅ |

Generate a packet with `POST /api/v1/applications/{id}/materials/generate`, inspect it with `GET /api/v1/applications/{id}/materials`, and approve only after review with `POST /api/v1/applications/{id}/review`. The approval path still cannot submit an application; the existing state machine enforces the stop-before-submit boundary.

## Phase 3 — Matching

Phase 3 adds deterministic, explainable matching between normalized jobs and selected candidate profile versions.

| Feature | Status |
|---------|--------|
| Hard eligibility constraints (remote, location, employment type) | ✅ |
| Weighted normalized skill/title/experience/education scoring | ✅ |
| Persisted fingerprinted match results with idempotent upsert | ✅ |
| Match read API and safe refresh API | ✅ |
| Shared TypeScript match contract and dashboard view | ✅ |
| Application state and submission path unchanged | ✅ |

Refresh matches without application side effects:

```bash
curl -X POST http://localhost:8000/api/v1/matches/refresh \\
  -H 'content-type: application/json' \\
  -d '{"profile_id":"<candidate-id>","profile_version":1,"job_ids":["<job-id>"],"constraints":{"remote_only":true}}'
```

Read results with `GET /api/v1/matches` or open the dashboard Matches view. A changed job snapshot, profile version, or constraint input produces a new fingerprinted result.

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
cd services/api && uv run pytest tests/test_matching.py tests/test_matches_api.py
npm run typecheck --workspaces --if-present
npm run build --workspace @career-pilot/dashboard
cd db && uv run alembic check
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
