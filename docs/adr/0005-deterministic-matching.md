# ADR 0005: Deterministic Profile Matching

- **Status:** Accepted
- **Date:** 2026-07-28

## Decision

Phase 3 computes eligibility and match scores locally from normalized jobs and an explicitly selected candidate profile version. Hard constraints (remote-only, allowed locations, and employment types) reject a match with human-readable reasons. Eligible records receive transparent weighted overlap scores for skills (50%), title (20%), experience (20%), and education (10%). Tokenization is lower-case, punctuation-aware, stopword-filtered, and deterministic.

Each result is stored in `matches` with the job snapshot, candidate profile/version, constraints, and all normalized inputs represented by a SHA-256 `input_fingerprint`. The unique key `(job_id, candidate_profile_id, profile_version, input_fingerprint)` makes refresh idempotent while retaining a new result when a job snapshot, profile version, or constraint changes.

## API boundary

- `GET /api/v1/matches` lists persisted results.
- `GET /api/v1/matches/{match_id}` reads one result.
- `POST /api/v1/matches/refresh` computes or retrieves results for a selected profile version and optional job list.

The refresh endpoint only writes match records. It does not create, update, or transition applications and does not contact employer sites.

## Consequences

The model is explainable and reproducible without external LLM/API calls. Matching is intentionally conservative for malformed profile data: invalid list-shaped fields are treated as empty rather than raising or inventing evidence. Future semantic models may be added as a separate versioned scoring strategy without changing the initial stop-before-submit boundary.
