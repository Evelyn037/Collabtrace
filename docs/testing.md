# Testing

## Automated verification

Run the Backend suite from the repository root:

```powershell
cd collabtrace-backend
python -m pytest
```

Backend tests use temporary SQLite databases, mock GitHub transports/services and mock SMTP transports. They cover configuration, normalization, persistence, sync deduplication/update/failure behavior, authentication, registration and verification codes, System/Repository Role separation, mapping, Evidence, analytics, RCI invariants, release-sensitive logging and safe SMTP errors. Automated tests never send real email or require a real GitHub token.

Run each Frontend quality gate separately:

```powershell
cd collabtrace-frontend
npm run typecheck
npm run lint
npm test
npm run build
```

- `typecheck` runs TypeScript compiler checks for application and Vite configuration.
- `lint` runs ESLint with JavaScript/TypeScript recommended rules, React Hooks rules and Fast Refresh export checks.
- `test` runs Vitest, Testing Library and jsdom tests with mocked API modules.
- `build` repeats type checking and creates the Vite production bundle.

Run repository release checks from the root:

```powershell
python scripts/check_release_hygiene.py
```

The checker reads Git tracked files only. It rejects local environments, dependency/build/cache directories, databases and backups, credential-shaped values, non-placeholder sensitive assignments, private keys and obvious developer-specific absolute paths without printing secret values.

## Continuous integration

`.github/workflows/ci.yml` runs three independent jobs for pushes and pull requests:

1. Backend dependency installation and pytest on Python 3.12.
2. Frontend `npm ci`, typecheck, ESLint, tests and build on Node 22.
3. Dependency-free repository hygiene validation.

CI uses test-only placeholder secrets, mocks external services and requires no repository credentials.

## Manual smoke checklist

- Authentication: password login, email-code login, registration, logout, invalid and disabled handling.
- Repository: Analyze, first-admin assignment, selector, role-aware Sync and Sync History.
- RCI: Research Baseline, Custom Weights, active dimensions, coverage, medals and disclaimer.
- Invariance: Contribution Composition and Evidence do not change with personal weights.
- Explainability: Calculation Basis and Why This RCI agree with API fields.
- Evidence: original GitHub URL opens in a new tab with `noopener noreferrer`.
- Authorization: System Admin and Repository Admin controls remain independent; direct unauthorized API calls fail.
- Empty/error states: 401, 403, 404, missing data, empty analytics and failed sync.
- Responsive layout: header, selector, mountain, dialogs, Evidence and Admin Center.
- Optional integration: bounded Analyze against a public repository and a separately authorized real SMTP inbox test.

## Test scope

Passing automated checks confirms the current covered behavior; it is not a claim of 100% coverage, load testing, penetration testing, cross-browser certification, complete GitHub history or production SMTP availability. Record exact test counts in a dated release report rather than hard-coding them in this maintained guide.
