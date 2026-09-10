# CollabTrace Backend

The CollabTrace API collects bounded GitHub repository activity, normalizes it into Contribution Events, persists it in SQLite and exposes authenticated analytics, RCI, Evidence, repository administration and account APIs to the React frontend.

## Runtime and dependencies

- Python 3.11+
- FastAPI and Pydantic
- SQLAlchemy 2 with SQLite
- HTTPX GitHub REST API client
- PyJWT and Argon2id password hashing
- pytest

Direct dependencies are pinned in `requirements.txt`. Create a project-local virtual environment rather than installing them globally.

## Fresh setup

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.cli init-jwt-secret
python -m app.cli init-verification-secret
python -m uvicorn app.main:app --reload
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m app.cli init-jwt-secret
python -m app.cli init-verification-secret
python -m uvicorn app.main:app --reload
```

The CLI writes generated secrets only to the ignored local `.env`. API documentation is available at `http://127.0.0.1:8000/docs`; `GET /health` reports the service name and version.

## Configuration

`.env.example` is the complete safe template. Important groups are:

- GitHub: `GITHUB_TOKEN` is optional for public repositories but increases API limits.
- Database: `DATABASE_URL` defaults to `sqlite:///./data/collabtrace.db`.
- Authentication: `JWT_SECRET`, algorithm and expiration.
- Verification: an independent `VERIFICATION_CODE_SECRET` and `console` or `smtp` provider.
- SMTP: host, port, username, authorization credential, sender and STARTTLS setting.
- Collection: bounded Quick Analyze page and review limits.
- Browser access: exact `FRONTEND_ORIGINS` values.

`console` verification is for local development and prints the one-time code in the Backend terminal. `smtp` performs actual server-side delivery. Never commit either `.env`, credentials, generated secrets, database files or backups.

## Architecture

```text
HTTP routes
  → authentication and repository authorization dependencies
  → GitHub integration / business services
  → normalization and ContributionEvent persistence
  → analytics and RCI services
  → validated response schemas
```

GitHub Commit, Pull Request, Issue and Review data are normalized into a common event model. Sync upserts events by stable repository/event identifiers, records execution history and avoids duplicate Evidence. Dashboard analytics read persisted SQLite data instead of calling GitHub on every view.

## API areas

- `/api/auth`: password login, registration and email-code flows
- `/api/users`: System Admin account management
- `/api/repositories`: analyze, list, detail, sync and access management
- `/api/repositories/{id}/members`: contributor mapping
- `/api/repositories/{id}/...`: overview, timelines, Evidence and RCI
- `/api/github`: System Admin diagnostics
- `/health`: public service status and version

System Role and Repository Role are independent. Member Mapping affects attribution only and grants no authorization. See `../docs/api.md` and `../docs/permissions.md` for the current contract.

## Database

The course version uses `Base.metadata.create_all()` during application startup. A fresh database is created automatically. Existing SQLite data is not migrated or deleted by setup, and database files must stay outside Git. Formal migrations and a production database are deferred hardening work.

## Commands

```powershell
python -m pytest
python -m app.cli create-admin
python -m app.cli create-member
python -m app.cli grant-repository-admin
python -m app.cli cleanup-demo-data
```

`cleanup-demo-data` is dry-run by default; use `--apply` only after reviewing its exact plan. Tests use mocks and temporary databases and do not require a real GitHub token or SMTP credential.

## Security boundary

- Passwords are stored as Argon2id hashes.
- JWT and verification HMAC keys come from environment configuration.
- Verification codes expire, are attempt-limited and are stored only as HMAC digests.
- SMTP mode logs stages and exception classes but not credentials, codes, bodies or complete addresses.
- GitHub credentials stay in the Backend and never enter API responses.
- CORS accepts configured exact origins rather than a credentialed wildcard.
- FastAPI dependencies enforce System Admin and Repository Admin operations server-side.

This repository describes a local/self-hostable course application. It does not claim cloud deployment, real-time streaming, complete GitHub history, penetration testing or production SaaS readiness.
