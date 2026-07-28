# CareerPilot Build Specification

CareerPilot is a clean-room restart of a personal AI-powered job discovery and assisted-application workspace. It combines a polished React dashboard, structured candidate profile, public job discovery, deterministic and semantic matching, truthful document tailoring, reusable answers, observable workflows, and a browser-worker boundary.

## Initial release boundary

The initial version supports discovery, normalization, matching, packet preparation, review, and assisted navigation design. It **always stops before final submission**. No automated submission, CAPTCHA solving, identity-verification bypass, credential persistence, inbox-code retrieval, or security-control bypass is permitted.

The data model may represent a future per-application confirmation gate, but it must be disabled in the initial release. A future release may require explicit authorization tied to the exact résumé, answers, packet fingerprint, job snapshot, and final browser state.

## Phase sequence

1. Foundation: monorepo, Docker Compose, schemas, dashboard shell, fake data, tests, CI.
2. Job discovery: Greenhouse/Lever/Ashby adapters, Crawl4AI generic crawler boundary, normalization, dedupe, scheduled runs.
3. Matching: deterministic eligibility plus semantic scoring and explanations.
4. Application materials: truthful résumé tailoring, diffs, cover letters, answer library, review gates.
5. Assisted application: visible Playwright worker, ATS adapters, approved-field filling, screenshots, stop-before-submit.
6. Advanced automation: resilient mapping, recovery, notifications, additional ATS support, future explicit confirmation.

## Reference boundaries

- `job-application-automation`: product and safety workflow reference only.
- `ApplyPilot`: AGPL-3.0-only reference; do not copy code or import its unsafe automation behavior.
- `Crawl4AI`: crawling/extraction architectural inspiration; respect robots.txt, rate limits, terms, authentication, and private-network protections.
