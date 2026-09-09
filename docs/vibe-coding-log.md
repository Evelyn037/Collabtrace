# Vibe Coding Log

Exact development dates and verbatim prompts were not recorded in the repository. This log is an objective phase summary reconstructed from current code, tests, documentation and acceptance results; missing historical details are marked **Not recorded**.

## Phase 1 — GitHub API Integration

- Goal: verify real Commit, Pull Request, Issue and Review collection.
- AI assistance summary: client/service structure, normalization and error handling support.
- Human decision: use GitHub REST data and bounded collection rather than mock production analytics.
- Validation: normalizer/client tests and repository probes.
- Problems found: rate limits and repositories without all activity types.
- Final result: real GitHub integration retained. Exact prompt/date: Not recorded.

## Phase 2 — Persistence, Sync and Analytics

- Goal: durable SQLite storage, deduplication, mapping, timelines and evidence.
- AI assistance summary: SQLAlchemy models, services, APIs and regression tests.
- Human decision: stable repository event IDs and non-destructive repeated sync.
- Validation: insert/update/unchanged, failure and analytics tests.
- Problems found: partial GitHub metadata requires explicit coverage reporting.
- Final result: persistent evidence pipeline. Exact prompt/date: Not recorded.

## Phase 3 — Authentication and RBAC

- Goal: JWT authentication, local users, registration/code login and permission boundaries.
- AI assistance summary: credential/contact/code models, guards and System User APIs.
- Human decision: passwords use Argon2id; secrets stay in environment; only ADMIN/MEMBER stored roles.
- Validation: login, disabled account, registration, code, 401/403 and secret-response tests.
- Problems found: System Role initially risked being confused with Repository ownership.
- Final result: authenticated full stack. Exact prompt/date: Not recorded.

## Phase 3B — Product UI and Repository-scoped IA

- Goal: production frontend, repository switching, Dashboard, evidence and separated admin surfaces.
- AI assistance summary: React components, responsive styling, accessible modals and test coverage.
- Human decision: Repository Admin Center and System Users remain separate; UI uses Chinese-first product copy.
- Validation: frontend tests, build/lint and browser acceptance.
- Problems found: role labels, responsive layouts and medal legibility required several micro-polish passes.
- Final result: accepted frontend product. Exact prompt/date: Not recorded.

## RCI_V1

- Goal: transparent, quality-filtered, explainable relative contribution view.
- AI assistance summary: four-dimension normalization, filters, custom query weights and explanations.
- Human decision: equal-weight Research Baseline; custom preferences remain session-local; composition/evidence invariant.
- Validation: backend invariants, frontend weight flow and browser checks.
- Problems found: bounded metadata means coverage must be visible; RCI must not be framed as performance.
- Final result: RCI_V1 frozen. Exact prompt/date: Not recorded.

## Phase 4 — Final stabilization

- Goal: safe data cleanup, final regression, demo readiness and complete documentation.
- AI assistance summary: reviewed current implementation, added guarded cleanup CLI/tests, found and fixed cancelled sync status, executed audits and wrote delivery docs.
- Human decision: preserve real data with an online SQLite backup; delete only proven acceptance scope; no new business feature.
- Validation: recorded in `docs/testing.md` and the final acceptance report.
- Problems found: old acceptance accounts/artifacts and interrupted sync records needed controlled cleanup.
- Final result: recorded by the Phase 4 acceptance report.
