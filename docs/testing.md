# Testing

## Automated commands

```powershell
cd collabtrace-backend
python -m pytest

cd ..\collabtrace-frontend
npm test
npm run build
npm run lint
```

Backend tests cover normalization, persistence, sync dedup/update/failure/cancellation, authentication, registration/code flow, repository-scoped access, mapping, analytics and RCI invariants. Frontend tests cover authentication UI, routing/guards, repository role switching, admin separation, Dashboard RCI interactions, modal behavior, contributor evidence and medals.

## Phase 4 executed checks

- Baseline: Backend 55 passed; Frontend 36 passed; build and lint passed.
- Cleanup tool: dry-run selection, protected mixed-access account, safe mapping unlink and apply behavior.
- Live public repository Analyze against GitHub with bounded scope.
- Existing Repo MEMBER Analyze rejection with unchanged sync count.
- Repeated sync event-ID dedup and cancellation-to-FAILED behavior.
- Real SQLite RCI baseline/custom comparison, total tolerance, composition and Evidence invariance.
- Repository role and System Role separation through API/UI.
- Persistence across a controlled backend stop/start.
- Browser inspection at 1440, 1024 and 390, including console and request destinations.
- Secret-name/pattern scan and production hard-code scan.

Final regression: Backend 60 passed with 0 failures; Frontend 36 passed with 0 failures; production build and TypeScript lint passed. The backend emitted two third-party deprecation warnings plus a local pytest-cache permission warning; none affected runtime behavior or test results.

## Final engineering finalization

- Modification baseline: Backend 60 passed; Frontend 36 passed; lint and build passed.
- Added offline SMTP transport tests for timeout, STARTTLS, authenticated login, message sending, incomplete configuration, safe transport failure, console fallback and non-disclosure.
- Added FLOW log tests for Analyze/Sync stages, real persistence counts, failure visibility and secret non-disclosure.
- Built an isolated prospective release copy from the Git-ignore-filtered source set. It contained no local environment, database, backup, dependency or build directories.
- In that isolated copy, a new Python virtual environment installed `requirements.txt` and passed 69 Backend tests; a new `npm ci` installation passed 36 Frontend tests, lint and build. `/health` also returned successfully from the isolated Backend.
- This is not labeled a true clean checkout because the current Git repository has no first commit or `HEAD`. A genuine clone/archive validation must follow the reviewed baseline commit.
- Final working-tree regression passed 69 Backend tests, 36 Frontend tests, lint and build. The existing working directory's `npm ci` could not remove one stale native Rollup file because of a Windows ACL/lock (`EPERM`); `npm install` restored the local dependencies and the full frontend validation passed afterward. This local cleanup caveat does not affect the isolated successful `npm ci` result.
- `npm audit --omit=dev` reported three moderate advisories affecting ECharts and React Router. Available automatic fixes require major-version upgrades; they were not applied during feature freeze. Current chart labels are fixed metric/date labels and navigation targets are application-controlled, reducing exposure, but the dependency migrations remain release follow-up work.

## Manual E2E checklist

- Authentication: username/password, email/password, code login, registration, logout, invalid/disabled handling.
- Repository: create/analyze, loading, role assignment, selector, sync and history.
- RCI: baseline, custom values/ranking, active dimensions, coverage, medals and disclaimer.
- Invariance: same contributor composition and same Evidence before/after weights.
- Explainability: Calculation Basis and Why This RCI values match API fields.
- Evidence: real URL, new tab, `noopener noreferrer`.
- Empty/error: 401, 403, 404, missing repository, no contributors/timeline/evidence/sync history.
- Responsive: Header, selector, mountain, medals, weight/methodology/quick-view dialogs and Admin Center.

## Scope statement

This project does not claim load testing, penetration testing, 100% coverage, cross-browser certification or production SMTP delivery. `VERIFICATION_PROVIDER=console` verifies only the local console flow unless SMTP is separately configured and tested.
