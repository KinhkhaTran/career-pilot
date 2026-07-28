# ADR-0003: Monorepo with Turborepo and Isolated Python Services

**Status:** Accepted
**Date:** 2024-07-01
**Deciders:** CareerPilot project team

## Context

CareerPilot consists of multiple components that need to share type contracts but must remain independently deployable and testable:

- A Next.js dashboard (`apps/dashboard`)
- A FastAPI REST service (`services/api`)
- An ARQ background worker (`services/worker`)
- Shared TypeScript type contracts and Zod schemas (`packages/contracts`)
- Shared React UI primitives (`packages/ui`)

The question is how to structure the repository to maximize code sharing where appropriate while enforcing the isolation boundary between public job discovery/browser workers and the dashboard/API.

## Decision

All components live in a single Git repository (monorepo) managed by:

- **Turborepo** for JavaScript/TypeScript package orchestration, caching, and task running
- **npm workspaces** for Node.js dependency management
- **Separate Python `pyproject.toml` files** for each Python service (`services/api`, `services/worker`), each installable as an independent package

The Python services are intentionally not managed by a Python monorepo tool (e.g. Poetry workspaces). Each service has its own virtual environment, dependencies, and `pyproject.toml`. Shared Python utilities, if any, are published as internal packages rather than path dependencies.

The isolation boundary is enforced by structure:

```
services/api/      # API only; no browser automation imports
services/worker/   # Worker only; no direct DB writes from browser layer
```

## Rationale

- **Shared TypeScript contracts** eliminate drift between the API response shapes and the dashboard's type expectations. The `packages/contracts` workspace is consumed by both `apps/dashboard` and could be used by any future TypeScript tooling.
- **Independent Python services** allow each service to pin its own dependency versions, run its own tests in isolation, and be deployed independently without monorepo-level Python tooling.
- **Turborepo** provides incremental builds and remote caching for the JS layer, which is appropriate for Next.js and shared package builds.
- **Single repository** simplifies cross-cutting concerns: CI pipelines, secret scanning, prohibited-automation scanning, and ADR/documentation live in one place with a single audit trail.

## Consequences

- Contributors working only on the Python services do not need to install Node.js (and vice versa for JS-only contributors), but the CI pipeline runs both.
- TypeScript contract types must be manually kept in sync with Python Pydantic models. A future improvement would be to generate one from the other (e.g. generate TypeScript from OpenAPI, or generate Pydantic from JSON Schema).
- Turborepo task dependencies (`turbo.json`) must be kept accurate; stale task graphs silently skip rebuilds.
- The `fixtures/mock-ats` package is a placeholder; it is not consumed by anything in Phase 1 and exists only to reserve the namespace.

## Rejected Alternatives

- **Polyrepo (one repo per service)**: Rejected because sharing type contracts across repos requires publishing packages or using git submodules, both of which add friction to a small team working across all services simultaneously.
- **Poetry workspaces for Python**: Rejected because the Python services have sufficiently different dependency trees that a shared lockfile would create unnecessary coupling. Independent `pyproject.toml` files with their own lockfiles are simpler.
- **Nx instead of Turborepo**: Rejected for Phase 1. Turborepo is lighter weight and sufficient for the current task graph. Nx can be adopted later if the project requires its plugin ecosystem.
