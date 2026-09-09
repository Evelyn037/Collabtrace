# CollabTrace · 协作透镜

CollabTrace 从真实 GitHub Commit、Pull Request、Issue 与 Code Review 中构建可视化、可解释、可追溯的团队贡献视图。它解决课程团队项目中协作过程不可见、个人贡献难以客观说明、结论缺少原始证据链的问题。

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
- Username/Email + Password、Email Code、Registration、JWT 与账号禁用。
- System Role、Repository Role、Member Mapping 三套独立语义。
- Repository Admin Center 与独立的 System Users 信息架构。

## Architecture and stack

```text
Browser → React 19 + TypeScript + Vite
                    ↓ JSON / JWT
              FastAPI + SQLAlchemy
                 ↙             ↘
       GitHub REST API          SQLite
```

Frontend 不直接请求 `api.github.com`，GitHub Token 只存在后端环境。详细数据流见 [Architecture](docs/architecture.md)。

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, React Router, Axios, ECharts |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, HTTPX |
| Security | Argon2id password hash, signed JWT Bearer tokens |
| Persistence | SQLite |
| Tests | pytest, Vitest, Testing Library, jsdom |

## Directory structure

```text
collabtrace/
├── collabtrace-backend/   # API, GitHub integration, persistence, analytics
├── collabtrace-frontend/  # Product UI
├── docs/                  # Architecture, API, RCI, permissions and demo docs
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
python -m app.cli init-verification-secret
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
python -m app.cli init-verification-secret
python -m uvicorn app.main:app --reload
```

The two `init-*` commands generate independent cryptographically random secrets and write them only to the ignored local `.env`. As an alternative, generate each value locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`; never reuse a secret published in documentation.

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

Backend `.env.example` defines `GITHUB_TOKEN`, `DATABASE_URL`, JWT settings, verification provider/secret, SMTP settings, quick-analyze limits and CORS origins. Frontend only needs `VITE_API_BASE_URL`.

- Public GitHub repositories work without a PAT, but rate limits are lower.
- `VERIFICATION_PROVIDER=console` prints one-time codes to the backend console for local development; it is not real email delivery.
- `VERIFICATION_PROVIDER=smtp` uses server-side SMTP. For QQ Mail, use `smtp.qq.com`, port `587`, STARTTLS, the complete QQ email address and a QQ SMTP authorization code—not the QQ login password.
- Never commit `.env`, JWT/verification secrets, SMTP credentials, SQLite databases or backup databases.

The complete required/optional/default/recommendation matrix and QQ instructions are in [Deployment](docs/deployment.md). A deployed instance uses the server operator's configured sender; end users do not configure SMTP themselves.

## First System Admin and demo accounts

Create the first System Admin locally:

```powershell
python -m app.cli create-admin
```

Passwords are entered interactively and are never accepted as command-line arguments. Demo accounts must be created or prepared locally; no credentials are stored in this repository.

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
npm test
npm run build
npm run lint
```

The Phase 4 test record and manual verification scope are in [Testing](docs/testing.md). No claim is made for load testing, penetration testing or 100% coverage.

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

Before release, run `python scripts/check_release_hygiene.py`. For a reviewed repository with a real commit, create a submission archive with:

```powershell
git archive --format=zip --output=collabtrace-submission.zip HEAD
```

`git archive` packages only committed files, which prevents ignored local `.env`, databases, backups, virtual environments and `node_modules` from being copied accidentally. Review the archive before submission. Do not use it until a real baseline commit exists.

## Documentation

- [Architecture](docs/architecture.md)
- [Core API](docs/api.md)
- [RCI Methodology](docs/rci-methodology.md)
- [Permissions](docs/permissions.md)
- [Demo Guide](docs/demo-guide.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Product Rationale](docs/product-rationale.md)
- [Vibe Coding Log](docs/vibe-coding-log.md)
- [Team Contributions](docs/team-contributions.md)
