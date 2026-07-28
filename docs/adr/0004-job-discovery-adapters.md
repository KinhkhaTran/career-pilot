# ADR 0004 — Public ATS Adapters and Generic Crawler Boundary

**Status:** Accepted
**Date:** 2024-07-15

## Context

Phase 2 introduces read-only job discovery from three public ATS platforms: Greenhouse, Lever, and Ashby. Each exposes an unauthenticated public job-board JSON API. We also need a boundary interface for a generic crawler (Crawl4AI-compatible) that could handle arbitrary job boards in a future phase.

The design must:
- Never require credentials, cookies, CAPTCHA solving, or session state.
- Respect platform rate limits and `robots.txt`.
- Be testable without live network calls (deterministic fixtures).
- Remain isolated from the dashboard and API — the worker handles all discovery I/O.
- Produce deterministic, content-addressable job snapshots for deduplication.

## Decision

### Adapter interface

Each adapter implements `ATSAdapter` (abstract base in `services/worker/app/adapters/base.py`). The interface exposes:

- `discover_jobs() -> AsyncIterator[RawJobPosting]` — yields raw job postings; no `company_id` parameter since adapters are constructed with their company identifier.
- `health_check() -> bool` — checks reachability of the ATS endpoint.

`RawJobPosting` is a frozen dataclass carrying the minimum structured fields plus a `raw_data: dict` for the full original response.

### Normalization

A stateless `normalize` function in `services/worker/app/adapters/normalizer.py` converts `RawJobPosting` → `NormalizedJobData`. This layer:
- Strips HTML using `html.parser` from the standard library.
- Extracts `is_remote` heuristically from title, location, and description text.
- Infers `employment_type` from commitment/type fields.
- Computes a deterministic `snapshot_hash` as `SHA-256(source|external_id|title|description)`.

Normalization is pure (no I/O) and fully unit-testable.

### Deduplication

Jobs are deduplicated at the DB layer using the `UNIQUE(source, external_id)` constraint already in the `jobs` table. On conflict, the worker updates the row only if `snapshot_hash` differs (indicating the job content changed). If the hash is unchanged the row is skipped; this makes every discovery run idempotent.

### Discovery runs

Each scheduled or manual discovery run is tracked in `discovery_runs` with an idempotency key. An append-only `discovery_run_events` table records milestones (run started, completed, failed). This mirrors the application event log pattern established in Phase 1.

### Generic crawler boundary

`services/worker/app/crawler/boundary.py` defines a `CrawlerBoundary` Protocol that future generic-crawler adapters must satisfy. It specifies `fetch(url, ...)→ CrawlResult`. No Crawl4AI dependency is introduced in Phase 2; the interface exists only as a boundary contract.

### Retry and timeout policy

HTTP calls use `httpx.AsyncClient` with:
- `timeout=30.0s`
- Up to 3 retries with exponential backoff (2s, 4s, 8s) on 5xx or network errors.
- No retry on 4xx (client error).

Retries are implemented in-process without external libraries.

## Consequences

- ATS adapters are fully isolated behind the `ATSAdapter` interface, making it trivial to add more sources in later phases.
- Deterministic fixtures in `fixtures/mock-ats/` enable offline unit tests for every adapter without live network calls.
- The generic crawler boundary is defined but not wired — future phases can add a Crawl4AI adapter without changing existing code.
- The worker now depends on `sqlalchemy[asyncio]` and `asyncpg` to write discovery results directly to PostgreSQL, avoiding an HTTP round-trip through the API service.
- Discovery run events are append-only, consistent with the Phase 1 application event log design.

## Rejected alternatives

- **API-mediated writes**: Having the worker POST discovery results to the API service adds latency and a circular service dependency. Rejected in favour of direct DB access.
- **Single shared models package**: Creating a `packages/db` Python package for shared SQLAlchemy models is the right long-term approach but adds monorepo complexity beyond Phase 2 scope. The worker uses SQLAlchemy Core tables to avoid duplicating ORM models.
- **Polling for `robots.txt`**: All three target APIs (`boards-api.greenhouse.io`, `api.lever.co`, `api.ashbyhq.com`) have documented public job-board endpoints. We read their public API responses directly and do not scrape HTML pages.
