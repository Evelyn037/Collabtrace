# CollabTrace GitHub API PoC

## 1. 当前阶段目标

当前项目不是完整 CollabTrace，而是 GitHub API Deep Integration 第一阶段技术验证：确认能否稳定、完整、正确地获取真实仓库的 Commit、Pull Request、Issue 与 Code Review。

## 2. Architecture

```text
GitHub
  ↓
GitHub REST API
  ↓
FastAPI Backend
  ↓
Normalization
  ↓
ContributionEvent
```

## 3. Requirements

- Python 3.11+

## 4. Installation

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中按需配置 `GITHUB_TOKEN=`。公开仓库允许不配置 Token，但未认证 API 的 rate limit 更低，因此推荐使用最小权限 Token。不要把 Token 发给他人或提交到 Git。

## GitHub Token Configuration

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后由用户本人编辑 `.env`：

```dotenv
GITHUB_TOKEN=YOUR_GITHUB_TOKEN
```

Token 可在 GitHub 的 **Settings → Developer settings → Personal access tokens → Fine-grained tokens** 创建。PoC 只需最小的公开仓库读取权限，不要授予不必要的写权限。Token 通常只完整显示一次，绝不能提交到 Git。

启动服务后访问 `http://127.0.0.1:8000/api/github/auth-status`。有效 Token 会显示 `token_configured=true`、`authentication_mode=token` 以及 GitHub 实际返回的 rate limit；无效 Token 会明确返回 401，不会静默回退。服务会在每次请求时重新读取 `.env`，但修改配置后仍建议重启开发服务器。

## 5. How to run

```bash
uvicorn app.main:app --reload
```

Swagger UI：http://127.0.0.1:8000/docs

## 6. Test Repository

任意公开仓库均可：`GET /api/github/OWNER/REPO/probe`。不要把测试逻辑绑定到特定仓库；若目标仓库没有 Review，换用有真实 PR Review 的仓库验证。

## 7. API endpoints

- `GET /health`
- `GET /api/github/auth-status`
- `GET /api/github/{owner}/{repo}`
- `GET /api/github/{owner}/{repo}/commits`
- `GET /api/github/{owner}/{repo}/pulls`
- `GET /api/github/{owner}/{repo}/issues`
- `GET /api/github/{owner}/{repo}/reviews`
- `GET /api/github/{owner}/{repo}/probe`

列表和 probe 接口接受 `max_pages`（默认 10）；Review 相关接口还接受 `max_prs_for_reviews`（默认 50）。参数设为 `0` 可取消对应限制。

## 8. GitHub data collected

- Commit：代码历史与作者证据。
- Pull Request：分支合并提案及状态。
- Issue：任务或缺陷；GitHub Issues API 混入的 PR 会被过滤。
- Code Review：PR 审阅者、状态、时间与证据链接。

## 9. ContributionEvent

四种异构数据统一为 `ContributionEvent`，让后续分析只依赖稳定模型。`event_id` 使用 `commit:`、`pr:`、`issue:`、`review:` 前缀避免源 ID 冲突，必要补充数据放入 `metadata`。

## 10. Pagination

Client 使用 `per_page=100` 并依据响应数量和 `Link` header 继续翻页，不会停在 GitHub 默认的前 30 条。默认最多 10 页，避免大型仓库产生意外请求；传 `max_pages=0` 可读取全部。`probe.pagination` 会逐类标记 `possibly_truncated`，避免把受限数量误解为完整总数。

## 11. Rate Limit

Client 记录最近响应的 `X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Reset`。未认证请求额度较低；剩余额度很低时会停止不必要的分页或在 probe 返回 warning。

## 12. Security

Token 仅从后端 `.env` 读取；`.env` 已被 Git 忽略。响应、probe 文件及日志均不包含 Token 或 Authorization header。

## 13. Phase 1 scope

Phase 1 不包含 Database、Login、Member Mapping、Dashboard、Contribution Score 或 Deployment；`data/last_probe.json` 只是 GitHub API PoC 的本地调试快照。Phase 2 数据持久化能力见下文，Login、Dashboard、Contribution Score 与 Deployment 仍未实现。

# Phase 2 — Data Persistence & Repository Sync

Phase 2 在保留全部 GitHub API PoC 接口的基础上，新增 SQLite、SQLAlchemy 2.x、Repository、Member Mapping、持久化 ContributionEvent、可重复 GitHub Sync、去重以及基础 Analytics。当前课程阶段使用 `Base.metadata.create_all()` 建表；未来生产项目可升级为 Alembic migrations。

## Phase 2 Architecture

```text
GitHub Repository
        ↓
GitHub REST API
        ↓
GitHubService
        ↓
ContributionEvent
        ↓
SyncService
        ↓
Member Mapping
        ↓
SQLite Database
        ↓
AnalyticsService
        ↓
REST API
```

默认数据库配置为：

```dotenv
DATABASE_URL=sqlite:///./data/collabtrace.db
```

如果 `.env` 中没有 `DATABASE_URL`，系统自动使用该值。数据库文件属于本地运行数据，已由 `.gitignore` 排除。

## Phase 2 Data Models

- `User`：为未来登录和角色区分预留；当前不包含密码、JWT 或登录 API。
- `Repository`：保存经过 GitHub 验证的仓库信息，`full_name` 唯一。
- `Member`：课程项目成员与 GitHub username 的显式映射；同一仓库内 username 小写化且唯一。
- `ContributionEventRecord`：Phase 1 `ContributionEvent` 的持久化记录，通过 `(repository_id, event_id)` 数据库唯一约束去重。
- `SyncRecord`：记录每次同步的 RUNNING、SUCCESS 或 FAILED 状态及计数。

未知 GitHub contributor 不会自动成为 Member，其事件保留 `author_login` 且 `member_id=null`。

## Phase 2 API

- `POST /api/repositories`
- `GET /api/repositories`
- `GET /api/repositories/{id}`
- `POST /api/repositories/{id}/members`
- `GET /api/repositories/{id}/members`
- `PATCH /api/repositories/{id}/members/{member_id}`
- `POST /api/repositories/{id}/sync`
- `GET /api/repositories/{id}/syncs`
- `GET /api/repositories/{id}/events`
- `GET /api/repositories/{id}/unmapped-contributors`
- `GET /api/repositories/{id}/overview`
- `GET /api/repositories/{id}/member-stats`
- `GET /api/repositories/{id}/members/{member_id}/timeline`
- `GET /api/repositories/{id}/timeline`

## Sync Process

`POST /api/repositories/{id}/sync` 复用 Phase 1 `GitHubService`：

```text
Fetch → Normalize → Map → Deduplicate → Persist
```

新事件执行 INSERT，变化事件执行 UPDATE，未变化事件计为 UNCHANGED。数据库唯一约束确保重复同步不会重复保存。失败同步不会删除历史数据，并会单独保存 FAILED SyncRecord。

## Local Phase 2 Verification

1. 启动服务：

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

2. 在 Swagger 中调用 `POST /api/repositories`，请求体使用待验证的真实 `owner` 和 `repo`。
3. 调用 `POST /api/repositories/{id}/members` 创建显式成员映射。
4. 调用 `POST /api/repositories/{id}/sync?max_pages=1&max_prs_for_reviews=5`。
5. 使用完全相同参数再次同步，确认 `inserted=0` 且事件总数不翻倍。
6. 查看 `/overview`、`/member-stats`、`/events`、`/unmapped-contributors` 和成员 `/timeline`。
7. 重启服务并再次调用 `GET /api/repositories`，确认 SQLite 持久化数据仍存在。

Analytics API 只读取 SQLite，不会临时请求 GitHub。当前统计仅包括 Commit、PR、Issue、Review 数量、时间线及 mapped/unmapped，不包含 Contribution Score。

## Phase 2 scope

Phase 2 不包含 Frontend、Login、JWT、Admin 权限、Contribution Score、OAuth、Webhook、Docker 或云部署。Phase 3A 的 Login、JWT 与角色权限见下文；其他能力仍未实现。

# Phase 3A — Authentication & Role Separation

Phase 3A 新增 JWT Bearer Authentication 与后端 Role-Based Access Control（RBAC）。密码使用 pwdlib 提供的 Argon2id 哈希，JWT 使用 PyJWT 签名；角色仅包含 `ADMIN` 与 `MEMBER`。

为保护已经存在的 Phase 2 数据库，本阶段没有修改或删除 `users` 表，而是通过 `create_all()` 增量创建一对一的 `user_credentials` 表，保存 Argon2 password hash 与账号启用状态。

## Authentication Configuration

`.env.example` 包含：

```dotenv
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

不要在代码、README 或 Git 中保存真实 JWT Secret。首次运行时由用户主动执行：

```powershell
python -m app.cli init-jwt-secret
```

该命令使用安全随机数生成 Secret，只更新 `.env` 中的 `JWT_SECRET`，不会输出 Secret，也不会覆盖 GitHub Token。

## First Admin

交互创建首个管理员：

```powershell
python -m app.cli create-admin
```

密码通过 `getpass` 隐藏输入且需要二次确认，不支持命令行 `--password`。其他本地维护命令：

```powershell
python -m app.cli create-member
python -m app.cli set-password USERNAME
```

## Login

公开登录接口：`POST /api/auth/login`

```json
{
  "username": "member1",
  "password": "YOUR_PASSWORD"
}
```

成功响应包含 `access_token`、`expires_in` 和安全的用户摘要，不包含 password hash。用户名会 trim 并按小写匹配。

## Swagger Authorization

1. 调用 `/api/auth/login`。
2. 复制响应中的 `access_token`。
3. 打开 Swagger 的 **Authorize**。
4. 在 `JWTBearer` 中输入纯 Token；Swagger 会自动添加 `Bearer` 前缀。
5. 调用受保护 API。

Swagger：http://127.0.0.1:8000/docs

## Permission Matrix

| Function | Admin | Member |
| --- | --- | --- |
| View Repository Data | Yes | Yes |
| View Member Stats | Yes | Yes |
| View Evidence / Timeline | Yes | Yes |
| View Sync History | Yes | Yes |
| Create Repository | Yes | No |
| Sync GitHub | Yes | No |
| Manage Member Mapping | Yes | No |
| View Unmapped Contributors | Yes | No |
| Manage Users | Yes | No |
| GitHub Diagnostics | Yes | No |

仅 `/health` 和 `/api/auth/login` 是公开接口。未登录访问受保护接口返回401；已登录但角色不足返回403。所有权限判断都在 FastAPI 后端执行。

## Auth APIs

- `POST /api/auth/login`：公开登录。
- `GET /api/auth/me`：读取当前用户。
- `GET /api/auth/me/memberships`：读取当前用户关联的 Repository Member Mapping。
- `POST /api/users`：ADMIN 创建用户。
- `GET /api/users`：ADMIN 查看用户列表。
- `PATCH /api/users/{user_id}`：ADMIN 修改 display name、role 或 active 状态。

## Phase 3A Security

- Password 从不以明文保存，数据库只保存 Argon2id hash。
- JWT 包含签发和过期时间，并验证签名、算法与有效期。
- Disabled user 无法登录；已有旧 Token 也会因数据库状态检查被拒绝。
- API 不返回 UserCredential 或 password hash。
- JWT、密码、Authorization Header 与 GitHub Token 不写入日志。
- GitHub Token 与 JWT Secret 仅保存在被 Git 忽略的后端 `.env`。

## Phase 3A Scope

当前仍没有 Frontend Dashboard、Contribution Score、OAuth、Webhook、Refresh Token、MFA 或云部署。

# Phase 3 Backend Completion

## Email verification and public registration

Phase 3A.1 adds additive `user_contacts` and `verification_codes` tables. Existing users remain valid without an email address. Verification codes expire after five minutes, have a 60-second resend cooldown and a five-attempt limit, are single-use, and are stored only as HMAC-SHA256 digests.

Initialize the verification secret once without printing it or overwriting other `.env` entries:

```powershell
python -m app.cli init-verification-secret
```

`VERIFICATION_PROVIDER=console` is the local-development default and writes the one-time code to the backend console only. `VERIFICATION_PROVIDER=smtp` uses the standard-library SMTP client and requires `SMTP_HOST` and `SMTP_FROM`; incomplete SMTP configuration returns 503.

Public authentication endpoints:

- `POST /api/auth/verification/send` — request a `REGISTER` or `LOGIN` code.
- `POST /api/auth/register` — create a verified `MEMBER`; registration does not log the user in automatically.
- `POST /api/auth/login` — accepts `identifier` (username or email) and remains compatible with the legacy `username` request field.
- `POST /api/auth/login/code` — sign in with a verified email and one-time code.

The admin user API accepts an optional email. Password hashes, verification digests, secrets, codes and Authorization headers are never returned by the API.

## Analyze any accessible GitHub repository

An ADMIN can call `POST /api/repositories/analyze` with either `owner/repo` or a GitHub repository URL. CollabTrace does not require the repository owner to match the CollabTrace user: any public repository, or private repository readable by the backend GitHub credentials, can be analyzed. Existing repositories are reused and synchronized again instead of returning a duplicate conflict.

The Analyze endpoint uses a bounded synchronization scope for responsiveness and GitHub API rate-limit control:

```dotenv
QUICK_ANALYZE_MAX_PAGES=1
QUICK_ANALYZE_MAX_PRS_FOR_REVIEWS=5
```

Its result represents the latest synchronized GitHub activity, not complete repository history. The existing repository sync endpoint keeps its prior defaults.

## Contributor analytics

Contributor identity comes from case-insensitive GitHub `author_login`. Member Mapping is optional: unmapped contributors remain visible and analyzable, while mapping enriches identity with `member_id`, `user_id` and `display_name` without changing activity totals.

- `GET /api/repositories/{id}/contributor-stats?exclude_bots=true`
- `GET /api/repositories/{id}/contributors/{username}`
- `GET /api/repositories/{id}/contributors/{username}/timeline`
- `GET /api/repositories/{id}/events?author_login={username}` for evidence

Usernames ending in `[bot]` are excluded from contributor stats by default and can be included with `exclude_bots=false`. Activity Rank is deterministic (`total_events` descending, username ascending) and measures activity volume only; it is not a quality score or final performance evaluation.

## Frontend development origin

Credentialed CORS uses the explicit `FRONTEND_ORIGINS` list, defaulting to `http://localhost:5173,http://127.0.0.1:5173`. Do not configure a wildcard origin with credentials.

# Phase 3B.1 — Repository-Scoped RBAC

Repository business permissions are repository-scoped. The existing `User.role`
is preserved for backward compatibility and system-level operations such as user
management and `/api/github/*` diagnostics; it does not grant administration of
every repository.

```text
User
  ├── Repository A → MEMBER
  ├── Repository B → ADMIN
  └── Repository C → MEMBER
```

`RepositoryAccess` stores the explicit User × Repository role with a unique
`(repository_id, user_id)` constraint. A missing row computes to `MEMBER`, so all
authenticated users retain read access to analyzed repositories. An explicit
`ADMIN` row is required for repository writes. Member Mapping remains an
independent User ↔ GitHub Contributor identity relation and never grants access.

Existing repositories are bootstrapped idempotently at startup: a repository
without an administrator is assigned to the earliest active global system admin.
If recovery is needed, run the interactive command below; it never requests a
password:

```powershell
python -m app.cli grant-repository-admin
```

Any authenticated account may analyze a repository that CollabTrace has not seen
before, and the successful creator becomes that repository's ADMIN without
changing `User.role`. Refreshing an existing repository requires its repository
ADMIN role. Access is managed through:

- `GET /api/repositories/{repository_id}/access`
- `PATCH /api/repositories/{repository_id}/access/{user_id}`

At least one repository administrator is always required; demoting the last one
returns HTTP 409.

| Function | Repo ADMIN | Repo MEMBER |
| --- | --- | --- |
| View Dashboard | Yes | Yes |
| View Evidence | Yes | Yes |
| Analyze New Repository | Yes | Yes |
| Refresh Existing Repository | Yes | No |
| Sync | Yes | No |
| Member Mapping | Yes | No |
| Access Management | Yes | No |

# Phase 3B.4 — RCI Analytics

`GET /api/repositories/{id}/contribution-index` 为所有已登录用户提供数据库只读的
`RCI_V1` 结果。可选 query 为 `exclude_bots`、`weight_code`、`weight_pr`、
`weight_issue`、`weight_review`；自定义模式下所有 active dimension 都为零会返回 422。
响应包含 requested/effective weights、active dimensions、metric coverage、RCI/activity
双排名、四维 normalized score、未加权 composition、原始有效指标和每维 RCI contribution。

同步阶段在现有 `metadata_json` 中缓存 bounded commit detail 与 review comment 信息；
Dashboard 请求不会访问 GitHub。同步补充 `parents/stats/files`、PR draft/merge、Issue
state reason、Review author/snapshot/body/inline comment 等字段，同时保持既有 event id、
唯一约束、映射和证据 URL。
