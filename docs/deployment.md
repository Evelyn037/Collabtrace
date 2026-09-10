# Deployment and Reproducibility

CollabTrace V1 is a local/self-hostable full-stack application. No cloud deployment is included. It can run on another machine or server after dependencies and environment variables are configured.

## Local development and fresh clone

Prerequisites are Git, Python 3.11+ and Node.js 20.19+ or 22.12+ with npm, as required by Vite 7. Clone the repository, then follow the platform-specific Backend and Frontend commands in the root README. A fresh machine must create its own `.venv`, install Python requirements, run `npm ci`, and create local `.env` files from the examples. It does not need the original developer's `.venv`, `.deps`, `node_modules`, database or secrets.

SQLite tables are created on Backend startup. The default database is `collabtrace-backend/data/collabtrace.db`; preserve and back it up when it contains useful synchronized data. Backend direct dependencies are pinned in `requirements.txt`; Frontend dependency resolution is locked by `package-lock.json` and installed with `npm ci`.

## Environment configuration

| Variable | Required | Development default | Deployment recommendation |
|---|---|---|---|
| `GITHUB_TOKEN` | Optional | Empty; lower public API limit | Fine-grained PAT with only the access actually needed |
| `DATABASE_URL` | Yes | `sqlite:///./data/collabtrace.db` | Persistent writable volume/path |
| `JWT_SECRET` | Yes | No shared default | Independent random value, at least 48 random bytes |
| `JWT_ALGORITHM` | Yes | `HS256` | Keep `HS256` unless code and migration are reviewed |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | `480` | Choose an appropriate session lifetime |
| `VERIFICATION_CODE_SECRET`, `VERIFICATION_PROVIDER` | No; legacy only | Empty / `console` | Inactive compatibility subsystem; not used by registration or login |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_STARTTLS` | No; legacy only | Empty / `587` / `true` | Inactive compatibility configuration; not a production dependency |
| `QUICK_ANALYZE_MAX_PAGES` | Yes | `1` | Keep bounded for interactive Analyze |
| `QUICK_ANALYZE_MAX_PRS_FOR_REVIEWS` | Yes | `5` | Keep bounded for interactive Analyze |
| `FRONTEND_ORIGINS` | Yes | Local 5173 origins | Comma-separated exact deployed frontend origins |
| `VITE_API_BASE_URL` | Frontend build/runtime | `http://127.0.0.1:8000` | Public URL of the deployed FastAPI service |

Generate the JWT secret with `python -m app.cli init-jwt-secret` or independently with Python's `secrets` module. Never commit generated values.

## Password-only authentication

The active V1 account flow has no email-delivery dependency:

```text
Register: nickname + email + password + confirm password
Login: nickname or email + password
```

The API and database continue to use `username` as the nickname identity. Email is normalized and unique, but it is not verified ownership. Public registration always creates a global `MEMBER`; repository administration remains separately scoped.

The legacy verification table, provider modules and optional environment names remain only to avoid destructive database/code cleanup. No public verification route is mounted, and normal startup, registration and login never require or call SMTP.

## Frontend/backend cross-origin configuration

`VITE_API_BASE_URL` tells the frontend where FastAPI is available. Every browser origin that may call FastAPI must appear exactly in `FRONTEND_ORIGINS`, including scheme and port. Avoid wildcard credentialed CORS.

## Secret management

- Keep `.env`, PATs, JWT secrets, verification secrets and SMTP authorization codes outside Git.
- Never publish SQLite files or backups containing user and verification metadata.
- Rotate a credential immediately if it was committed or exposed; removing only the latest file does not erase Git history.
- Run `python scripts/check_release_hygiene.py` before release.

## Safe GitHub release and ZIP packaging

Review `git status`, commit the reviewed source and leave the non-ignored tree clean. Then use:

```powershell
python scripts/create_submission_archive.py
```

The script runs `check_release_hygiene.py`, refuses a dirty tree, archives committed content only and inspects the resulting `submission/collabtrace-submission.zip` for forbidden paths. Directly compressing the development directory can accidentally include ignored credentials, databases and dependency directories.

## Fresh clone verification checklist

1. Confirm the checkout contains no `.env`, `*.db`, backup database, `.venv`, `.deps`, `node_modules`, `dist` or test artifact.
2. Create the Backend virtual environment and install `requirements.txt`.
3. Copy both `.env.example` files and generate a new JWT secret.
4. Run Backend tests and start `/health`.
5. Run `npm ci`, frontend typecheck, ESLint, tests and build.
6. Start the frontend and verify its configured API origin.
7. Register without a verification code, then verify both nickname/password and email/password login.

## Production hardening / future improvements

The current course release intentionally keeps SQLAlchemy automatic schema creation and SQLite. A production deployment would need persistent storage or a managed database, formal schema migrations, HTTPS, a reviewed secure-cookie/session strategy, managed secrets, monitoring, tested backup/restore and explicit deployment configuration. These are future improvements, not capabilities claimed or implemented by this repository.
