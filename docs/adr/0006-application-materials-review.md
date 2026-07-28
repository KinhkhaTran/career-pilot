# ADR 0006: Truthful Application Materials and Human Review

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

CareerPilot needs to prepare application materials without inventing candidate facts or allowing generated content to bypass human review. Candidate profiles are versioned, jobs have immutable discovery snapshots, and applications already have a stop-before-submit state machine.

## Decision

Phase 4 stores immutable, versioned résumé and cover-letter materials per application, plus versioned reusable screening answers. Résumé tailoring is a deterministic local transformation over profile claims; it may reorder and emphasize existing facts but cannot add unsupported claims. Each résumé revision stores a unified diff and its source claims.

Every generated packet receives a deterministic fingerprint containing the candidate profile version, résumé version, cover-letter version, answer versions, job snapshot hash, and rendered packet hash. Approval is allowed only while the application is in `human_review`, a packet fingerprint exists, and generated materials are present. Approval marks every material reviewed and transitions through the existing application state machine. No endpoint submits an application.

Candidate profile identifiers in answer-library rows are logical references rather than database foreign keys because `candidate_profiles.id` is intentionally shared by multiple version rows.

## Consequences

- Past material revisions remain auditable and cannot be overwritten.
- Any changed profile, job snapshot, answer, or material revision produces a different packet fingerprint.
- Human review is explicit and server-enforced.
- PDF/DOCX export and browser navigation remain future work; this phase stores truthful text and reviewable diffs only.
