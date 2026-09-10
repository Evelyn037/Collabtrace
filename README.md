# CollabTrace · 协作透镜

CollabTrace 是一个前后端分离的协作贡献分析系统。它从真实 GitHub Commit、Pull Request、Issue 与 Code Review 中构建可视化、可解释、可追溯的团队贡献视图，解决课程团队项目中协作过程不可见、个人贡献难以客观说明、结论缺少原始证据链的问题。

RCI（Relative Contribution Index，相对贡献指数）只描述当前仓库、当前同步范围内可验证的 GitHub 协作行为，不是绩效、能力、代码质量、工作时长或绝对劳动价值评分。

## Core problem

传统团队作业往往只展示最终产物：协作过程不透明、个人贡献难以客观说明，结论也缺少可回到原始 GitHub 记录的证据链。CollabTrace 将这些真实记录保存为可核验的团队协作视图。

```text
Problem: final deliverables do not fully explain the collaboration process
  ↓
Existing Evidence: GitHub already records Commit, PR, Issue and Review activity
  ↓
CollabTrace: collect → normalize → persist → analyze → explain
  ↓
Verification: Contributor Evidence → original GitHub record
```

CollabTrace provides evidence-supported collaboration interpretation, not automatic performance evaluation or absolute contribution truth. It is designed for university teaching teams, student project teams and repository administrators—not employee scoring.

## Main features

- GitHub REST API bounded sync，持久化真实协作记录并去重。
- Repository 情况总览、活动趋势、RCI 山峰排名与金银铜奖牌。
- Research Baseline、会话隔离的 Custom Weights、Contribution Composition 与 Why This RCI。
- Contributor Detail、Evidence 筛选及安全跳转到原始 GitHub 记录。
- Nickname/Email + Password、Registration、JWT 与账号禁用。
- System Role、Repository Role、Member Mapping 三套独立语义。
- Repository Admin Center 与独立的 System Users 信息架构。

## Architecture and stack

```text
Browser → React 19 + TypeScript + Vite
                    ↓ JSON / JWT
              FastAPI + SQLAlchemy
                 ↙             ↘
       GitHub REST API    SQLite (local) / PostgreSQL (public demo)
```

Frontend 不直接请求 `api.github.com`，GitHub Token 只存在后端环境。详细数据流见 [Architecture](docs/architecture.md)。

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, React Router, Axios, ECharts |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, HTTPX |
| Security | Argon2id password hash, signed JWT Bearer tokens |
| Persistence | SQLite locally; Neon PostgreSQL for the public demo |
| Tests | pytest, Vitest, Testing Library, jsdom |

## Directory structure

```text
collabtrace/
├── .github/workflows/       # Continuous integration checks
├── collabtrace-backend/   # API, GitHub integration, persistence, analytics
├── collabtrace-frontend/  # Product UI
├── docs/                  # Architecture, API, RCI, permissions and demo docs
├── scripts/               # Release hygiene and submission packaging
└── README.md
```

## Quick start

### Prerequisites

- Git
- Python 3.11 or newer
- Node.js 20.19+ or 22.12+ with npm (Vite 7 requirement)

### Backend · Windows PowerShell

```powershell
cd collabtrace-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.cli init-jwt-secret
python -m uvicorn app.main:app --reload
```

### Backend · macOS/Linux

```bash
cd collabtrace-backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m app.cli init-jwt-secret
python -m uvicorn app.main:app --reload
```

The `init-jwt-secret` command generates a cryptographically random signing secret and writes it only to the ignored local `.env`. As an alternative, generate a value locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`; never use a secret published in documentation.

Backend: `http://127.0.0.1:8000`; Swagger: `http://127.0.0.1:8000/docs`; Health: `http://127.0.0.1:8000/health`.

### Frontend · Windows PowerShell

```powershell
cd collabtrace-frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

On macOS/Linux use `cp .env.example .env`. Frontend: `http://localhost:5173`.

## Environment variables

Copy each committed `.env.example` to an ignored local `.env`. Empty secret fields have no shared default and must be generated locally.

| Variable | Required | Development default | Purpose / non-development recommendation |
|---|---|---|---|
| `GITHUB_TOKEN` | No for public repositories | Empty | Raises GitHub API limits; use a least-privilege fine-grained PAT |
| `DATABASE_URL` | Production only | `sqlite:///./data/collabtrace.db` | Neon PostgreSQL connection string stored only in the backend environment |
| `JWT_SECRET` | Yes | Empty | JWT signing; generate an independent random value |
| `JWT_ALGORITHM` | Yes | `HS256` | JWT algorithm used by the current implementation |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | `480` | Access-token lifetime |
| `VERIFICATION_CODE_SECRET`, `VERIFICATION_PROVIDER` | No; legacy only | Empty / `console` | Retained for compatibility with the inactive verification subsystem |
| `SMTP_*` | No; legacy only | Empty | Retained for compatibility; current registration and login never use SMTP |
| `QUICK_ANALYZE_MAX_PAGES` | Yes | `1` | Bounds interactive GitHub collection |
| `QUICK_ANALYZE_MAX_PRS_FOR_REVIEWS` | Yes | `5` | Bounds review collection |
| `FRONTEND_ORIGINS` | Yes | Local ports 5173 | Exact comma-separated browser origins; do not use wildcard credentialed CORS |
| `VITE_API_BASE_URL` | Frontend | `http://127.0.0.1:8000` | FastAPI base URL embedded by Vite |

- Public GitHub repositories work without a PAT, but rate limits are lower.
- Never commit `.env`, JWT/verification secrets, SMTP credentials, SQLite databases or backup databases.

The complete required/optional/default/recommendation matrix is in [Deployment](docs/deployment.md). Legacy verification configuration is not part of the active account flow.

## Database

SQLAlchemy selects the database from `DATABASE_URL`. Without a production override, CollabTrace continues to use `collabtrace-backend/data/collabtrace.db`; the existing local database is not migrated or uploaded. A PostgreSQL URL selects psycopg 3 and enables connection pre-ping for serverless wake-up recovery. `metadata.create_all()` safely creates missing tables in a fresh database without dropping existing data. Database files, backups, and connection URLs must never be committed or included in a submission archive.

## Authentication and authorization

Public registration accepts nickname (`username` in the API/database), email, password and password confirmation. Email is a unique login identifier but is not treated as verified ownership. Login accepts nickname or email plus password. Passwords are stored as Argon2id hashes and successful login returns a signed JWT. System roles govern System Users and GitHub diagnostics; repository roles independently govern Sync, Mapping and Access changes for one repository. Frontend guards improve navigation, but every protected operation is authorized again by FastAPI dependencies.

## GitHub integration

All GitHub REST API access occurs in the Backend. A PAT is optional for public repositories but recommended for higher rate limits; it must be read from the Backend environment and granted only the required repository read access. Collection is bounded, normalized into stable Contribution Events, persisted in SQLite and then read by analytics without another GitHub request.

## First System Admin and demo accounts

Create the first System Admin locally:

```powershell
python -m app.cli create-admin
```

Passwords are entered interactively and are never accepted as command-line arguments. Demo accounts must be created or prepared locally; no credentials are stored in this repository.

For the public demo, the same CLI can target Neon when the operator sets `DATABASE_URL` only in the current local process. Enter both the connection string and admin password interactively; never paste either into source, documentation, frontend variables, or chat. See [Deployment](docs/deployment.md).

A standard user who first analyzes a new repository automatically becomes that repository's `ADMIN`. An existing repository never grants elevated access merely because a user analyzes it again.

## Demo flow

Login → Analyze a public repository → inspect RCI Mountain → change Custom Weights → open Quick View → verify the donut remains unchanged → open Why This RCI → inspect Contributor Evidence → switch between ADMIN/MEMBER repositories → open Admin Center.

Live Analyze depends on GitHub availability and rate limits. Keep an already synchronized repository as the offline fallback. See [Demo Guide](docs/demo-guide.md).

## Relationship to GitHub native views

GitHub remains the code-hosting and collaboration source of truth. CollabTrace does not replace it: it organizes several GitHub activity types into a course-team interpretation layer with RCI, formation explanations, repository-scoped roles, Evidence filtering and links back to the original record.

## RCI summary

RCI_V1 uses Code Implementation, Pull Request, Issue and Code Review. Each active dimension is normalized within the current repository team; inactive dimensions are removed and the remaining weights are renormalized.

```text
RCI(d) = 100 × Σ effective_weight(m) × R_m(d)
```

Research Baseline gives active dimensions equal weight. Custom Weights are stored only in the current browser tab per user and repository; they do not alter repository data, Evidence, or the unweighted Contribution Composition. See [RCI Methodology](docs/rci-methodology.md).

## Permission summary

- `User.role`: System Role (`ADMIN` is displayed as System Admin; `MEMBER` as Standard User).
- `RepositoryAccess.role`: Repository-specific `ADMIN` or `MEMBER`.
- `Member Mapping`: optional identity link from a CollabTrace user to a GitHub contributor; it grants no permission.

See [Permissions](docs/permissions.md) for the complete matrix.

## Tests

```powershell
cd collabtrace-backend
python -m pytest

cd ..\collabtrace-frontend
npm run typecheck
npm run lint
npm test
npm run build

cd ..
python scripts/check_release_hygiene.py
```

`typecheck` runs TypeScript compiler checks; `lint` runs ESLint. Current automated scope and manual verification guidance are in [Testing](docs/testing.md). No claim is made for load testing, penetration testing or 100% coverage.

## Demo data safety

Never delete `collabtrace-backend/data/collabtrace.db` as a reset shortcut. Back up the database first. The cleanup command is dry-run by default:

```powershell
python -m app.cli cleanup-demo-data
python -m app.cli cleanup-demo-data --apply
```

Review every listed identifier before using `--apply`. The tool recognizes tightly defined automated acceptance account formats and protects accounts that retain access outside the candidate repository scope.

## Security notes

- Passwords are stored only as Argon2id hashes.
- JWT is held in browser `sessionStorage`, not durable local storage.
- Evidence links use a new tab with `noopener noreferrer`.
- GitHub credentials never enter frontend code or API responses.
- Sync scope is bounded; CollabTrace does not claim to analyze complete GitHub history.

Before release, commit the reviewed source and leave the non-ignored working tree clean. Then run:

```powershell
python scripts/create_submission_archive.py
```

The script runs release hygiene first, refuses a dirty tree, uses `git archive` to package only committed files, and verifies the ZIP contains no forbidden runtime paths. The output is `submission/collabtrace-submission.zip`. Never compress the development directory directly.

## Free public demo deployment

The deployment target is a Render Static Site, a Render Free Web Service, and Neon PostgreSQL. Render serves HTTPS, while Neon keeps application data off Render's ephemeral filesystem. The free backend may sleep after inactivity and can take about one minute to wake. This is a course demonstration and small-scale testing deployment, not an always-on or high-availability production claim. The complete setup and the independent local SQLite fallback are documented in [Deployment](docs/deployment.md) and [Defense Fallback](docs/defense-fallback.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Core API](docs/api.md)
- [RCI Methodology](docs/rci-methodology.md)
- [Permissions](docs/permissions.md)
- [Demo Guide](docs/demo-guide.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Defense Fallback](docs/defense-fallback.md)
- [Product Rationale](docs/product-rationale.md)
- [Vibe Coding Log](docs/vibe-coding-log.md)
- [Team Contributions](docs/team-contributions.md)
