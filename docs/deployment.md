# Deployment and Reproducibility

CollabTrace V1 is a local/self-hostable full-stack application. No cloud deployment is included. It can run on another machine or server after dependencies and environment variables are configured.

## Local development and fresh clone

Prerequisites are Git, Python 3.11+ and Node.js 20.19+ or 22.12+ with npm, as required by Vite 7. Clone the repository, then follow the platform-specific Backend and Frontend commands in the root README. A fresh machine must create its own `.venv`, install Python requirements, run `npm ci`, and create local `.env` files from the examples. It does not need the original developer's `.venv`, `.deps`, `node_modules`, database or secrets.

SQLite tables are created on Backend startup. The default database is `collabtrace-backend/data/collabtrace.db`; preserve and back it up when it contains useful synchronized data.

## Environment configuration

| Variable | Required | Development default | Deployment recommendation |
|---|---|---|---|
| `GITHUB_TOKEN` | Optional | Empty; lower public API limit | Fine-grained PAT with only the access actually needed |
| `DATABASE_URL` | Yes | `sqlite:///./data/collabtrace.db` | Persistent writable volume/path |
| `JWT_SECRET` | Yes | No shared default | Independent random value, at least 48 random bytes |
| `JWT_ALGORITHM` | Yes | `HS256` | Keep `HS256` unless code and migration are reviewed |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | `480` | Choose an appropriate session lifetime |
| `VERIFICATION_CODE_SECRET` | Yes | No shared default | Independent random value; do not reuse JWT secret |
| `VERIFICATION_PROVIDER` | Yes | `console` | `smtp` for real email; console is development only |
| `SMTP_HOST` | SMTP only | Empty | SMTP server hostname |
| `SMTP_PORT` | SMTP only | `587` | Provider's STARTTLS port |
| `SMTP_USERNAME` | Provider-dependent | Empty | Complete sender mailbox when authentication is used |
| `SMTP_PASSWORD` | Provider-dependent | Empty | SMTP authorization credential from secret storage |
| `SMTP_FROM` | SMTP only | Empty | Authorized sender email address |
| `SMTP_USE_STARTTLS` | SMTP only | `true` | Keep enabled for QQ port 587 |
| `QUICK_ANALYZE_MAX_PAGES` | Yes | `1` | Keep bounded for interactive Analyze |
| `QUICK_ANALYZE_MAX_PRS_FOR_REVIEWS` | Yes | `5` | Keep bounded for interactive Analyze |
| `FRONTEND_ORIGINS` | Yes | Local 5173 origins | Comma-separated exact deployed frontend origins |
| `VITE_API_BASE_URL` | Frontend build/runtime | `http://127.0.0.1:8000` | Public URL of the deployed FastAPI service |

Generate JWT and verification secrets with the provided `python -m app.cli init-*` commands or independently with Python's `secrets` module. Never commit generated values.

## QQ SMTP configuration

Enable SMTP in the QQ Mail account and create an SMTP authorization code. This code is not the QQ login password. Put the following values only in the ignored Backend `.env`:

```dotenv
VERIFICATION_PROVIDER=smtp
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=<complete QQ email address>
SMTP_PASSWORD=<QQ SMTP authorization code>
SMTP_FROM=<complete QQ email address>
SMTP_USE_STARTTLS=true
```

Restart FastAPI after changing the configuration, request a registration code using a real recipient you control, and confirm receipt in the inbox. Do not paste the authorization code into prompts, screenshots, source code or issue reports. Mock tests prove transport behavior but do not prove real QQ delivery.

When deployed, every user receives messages from the sender mailbox configured by the server operator. End users do not provide their own SMTP settings. Developers who clone and self-host CollabTrace must configure their own credentials.

## Frontend/backend cross-origin configuration

`VITE_API_BASE_URL` tells the frontend where FastAPI is available. Every browser origin that may call FastAPI must appear exactly in `FRONTEND_ORIGINS`, including scheme and port. Avoid wildcard credentialed CORS.

## Secret management

- Keep `.env`, PATs, JWT secrets, verification secrets and SMTP authorization codes outside Git.
- Never publish SQLite files or backups containing user and verification metadata.
- Rotate a credential immediately if it was committed or exposed; removing only the latest file does not erase Git history.
- Run `python scripts/check_release_hygiene.py` before release.

## Safe GitHub release and ZIP packaging

Review `git status`, create a genuine commit, and confirm the hygiene checker passes. Then use:

```powershell
git archive --format=zip --output=collabtrace-submission.zip HEAD
```

This archives committed content only. Directly compressing the development directory can accidentally include ignored credentials, databases and dependency directories. Always inspect the resulting ZIP before sharing it.

## Fresh clone verification checklist

1. Confirm the checkout contains no `.env`, `*.db`, backup database, `.venv`, `.deps`, `node_modules`, `dist` or test artifact.
2. Create the Backend virtual environment and install `requirements.txt`.
3. Copy both `.env.example` files and generate new local secrets.
4. Run Backend tests and start `/health`.
5. Run `npm ci`, frontend tests, lint and build.
6. Start the frontend and verify its configured API origin.
7. Configure SMTP only with credentials owned by the new operator; perform a real inbox smoke test separately.

The current working repository must have a real first commit before a true clean-checkout test or `git archive HEAD` can be performed.
