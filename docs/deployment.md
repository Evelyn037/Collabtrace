# Free Public Deployment and Reproducibility

CollabTrace V1 supports two independent environments:

```text
Public: Browser → Render Static Site → Render Free Web Service → Neon PostgreSQL
Local:  Browser → Vite frontend      → Local FastAPI            → SQLite
```

The public target is a free course demonstration and small-scale test deployment. It is not an always-on, high-availability, or enterprise service. No credit card, paid compute, Render persistent disk, custom domain, or paid Neon feature is required.

## Database selection

SQLAlchemy selects the database from the backend `DATABASE_URL`:

- Local default: `sqlite:///./data/collabtrace.db`.
- Public deployment: the secret PostgreSQL connection string copied from Neon's **Connect** dialog.

Standard `postgresql://` and legacy `postgres://` schemes are normalized in memory to SQLAlchemy's `postgresql+psycopg://` dialect. Query parameters such as `sslmode=require` and `channel_binding=require` remain unchanged. PostgreSQL connections use `pool_pre_ping=True` so a stale pooled connection can recover after serverless inactivity. SQLite alone receives `check_same_thread=False`.

Backend startup runs SQLAlchemy `metadata.create_all()`. This creates missing tables in a fresh Neon database and does not drop tables, truncate data, or copy the local SQLite database. The public backend must never use SQLite on Render's ephemeral filesystem.

## Environment configuration

| Variable | Local | Render backend | Notes |
|---|---|---|---|
| `DATABASE_URL` | SQLite default | Required Neon secret | Backend only; never expose or log it |
| `JWT_SECRET` | Required local secret | Required new production secret | Generate independently; do not reuse examples |
| `GITHUB_TOKEN` | Optional | Recommended | Backend-only least-privilege token; raises API limits |
| `FRONTEND_ORIGINS` | Local 5173 origins | Exact Render Static Site HTTPS origin plus optional local origins | Comma-separated; never `*` |
| `JWT_ALGORITHM` | `HS256` | `HS256` | Preserve current JWT semantics |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Operator choice | Preserve the reviewed session policy |
| `QUICK_ANALYZE_MAX_PAGES` | `1` | `1` | Bounds interactive GitHub collection |
| `QUICK_ANALYZE_MAX_PRS_FOR_REVIEWS` | `5` | `5` | Bounds review collection |
| `VERIFICATION_*`, `SMTP_*` | Optional legacy | Not required | Inactive authentication compatibility only |
| `VITE_API_BASE_URL` | Local backend URL | Render backend HTTPS URL | Public frontend build variable, not a secret |

Never paste `DATABASE_URL`, JWT secrets, PATs, or passwords into chat, Git, documentation, screenshots, frontend variables, or deployment logs.

## Neon preparation

Use the existing Neon Free project and PostgreSQL database. Do not enable Neon Auth, Functions, Object Storage, AI Gateway, or a paid plan.

1. In Neon, open the project and confirm the plan is Free.
2. Choose a region near the intended Render backend region.
3. Click **Connect** and keep the complete connection string, including its security query parameters.
4. Paste it directly into Render's backend `DATABASE_URL` secret field. Do not send it through chat.
5. For the pre-deployment integration gate, set the connection string only in the current local process using a hidden prompt:

```powershell
$env:DATABASE_URL = Read-Host -MaskInput "Neon DATABASE_URL"
python -m pytest tests/test_postgres_integration.py
Remove-Item Env:DATABASE_URL
```

The test creates missing schema objects, validates PostgreSQL behavior, and rolls back its generated smoke-test rows. It does not drop schema or copy local demo data.

## Render backend

Create **New → Web Service** from the connected GitHub repository.

| Setting | Value |
|---|---|
| Service plan | Free |
| Root Directory | `collabtrace-backend` |
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Region | Prefer the closest available region to Neon |

Set `DATABASE_URL`, `JWT_SECRET`, and optionally `GITHUB_TOKEN` only in the Web Service environment. SMTP and verification variables are not needed. Do not attach a persistent disk: all durable public data belongs in Neon.

The first deployment may initially use local origins in `FRONTEND_ORIGINS`. After the Static Site URL exists, update it to include that exact HTTPS origin and redeploy the backend.

Render Free Web Services spin down after 15 minutes without inbound traffic and may take about one minute to wake. Their local filesystem is ephemeral. Do not add cron pings, self-pings, uptime bots, or another keep-alive workaround.

## Production System Admin bootstrap

Render Free does not provide shell access. Create the first System Admin from a trusted local terminal while targeting Neon. The URL and password are entered interactively and removed from the process afterward:

```powershell
cd collabtrace-backend
$env:DATABASE_URL = Read-Host -MaskInput "Neon DATABASE_URL"
python -m app.cli create-admin
Remove-Item Env:DATABASE_URL
```

The CLI uses the same SQLAlchemy configuration and Argon2id password hashing as the server. There is no public administrator-creation endpoint and no hard-coded credential.

## Render frontend

Create **New → Static Site** from the same repository.

| Setting | Value |
|---|---|
| Root Directory | `collabtrace-frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |
| `VITE_API_BASE_URL` | Exact Render backend HTTPS origin |

Add this rewrite in the Static Site Redirects/Rewrites settings:

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | Rewrite |

The frontend environment must not contain `DATABASE_URL`, `GITHUB_TOKEN`, `JWT_SECRET`, or any Neon credential. `VITE_API_BASE_URL` is compiled into the public bundle, so changing it requires a rebuild.

## Public acceptance flow

Use an incognito browser and a small or medium public repository:

1. Open the Static Site over HTTPS and register with nickname, email, password, and confirmation.
2. Log in by nickname, log out, then log in by email.
3. Confirm the new global role is `MEMBER` / Standard User.
4. Analyze a new repository and confirm the creator receives Repository `ADMIN`, without becoming System Admin.
5. Verify Dashboard, Research Baseline, Custom Weights, Quick View, Calculation Basis, Contributor Detail, Evidence, and the original GitHub link.
6. Confirm weight changes do not alter Contribution Composition or Evidence.
7. Redeploy or restart the backend, then verify the user, repository, events, and SyncRecord still exist.
8. Inspect browser requests: application API traffic goes only to the Render backend. The frontend never calls Neon or GitHub as an API data source.
9. Check 1440px, 1024px, and 390px layouts, browser console, CORS, and mixed-content errors.

## Local defense fallback

Without a process-level production `DATABASE_URL`, local startup continues to use the existing SQLite database. Do not delete, migrate, rename, or upload it. After public deployment, rerun the full SQLite test suite and verify the prepared local login, Dashboard, RCI, Contributor, and Evidence flow. See [Defense Fallback](defense-fallback.md).

## Release and security checklist

1. Confirm no `.env`, database, backup, `.venv`, `node_modules`, `dist`, PAT, JWT secret, or Neon URL is tracked.
2. Run backend tests, frontend typecheck, lint, tests, and build.
3. Run `python scripts/check_release_hygiene.py` immediately before commit and push.
4. Stage only explicit Phase 5 files; never use `git add .`.
5. Push normally without force or history rewriting.

## Known limitations

- Render Free backend cold starts are expected after inactivity.
- Free service bandwidth, build minutes, and instance hours are limited by Render.
- Neon Free capacity and compute limits apply.
- `metadata.create_all()` is suitable for the current fresh deployment; future schema evolution needs formal migrations.
- SQLite remains the local defense fallback, not the public persistence layer.
- No availability, load, penetration-test, backup, or disaster-recovery guarantee is claimed.
