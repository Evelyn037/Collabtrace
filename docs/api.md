# Core API

Interactive OpenAPI is available at `/docs`. This guide describes business intent rather than duplicating the generated schema. Unless marked public, endpoints require `Authorization: Bearer <JWT>`.

## Authentication

| Purpose | Method and path | Permission | Main request → response | Important errors |
|---|---|---|---|---|
| Password login | `POST /api/auth/login` | Public | identifier/username + password → JWT and safe user summary | 401 invalid credentials, 403 disabled |
| Send code | `POST /api/auth/verification/send` | Public | email + `REGISTER`/`LOGIN` → provider message | 429 resend limit, 503 provider |
| Register | `POST /api/auth/register` | Public | username, email, code, password confirmation → Standard User | 409 duplicate, 422 validation/code |
| Code login | `POST /api/auth/login/code` | Public | email + six-digit code → JWT | 401/422 invalid or expired code |
| Current user | `GET /api/auth/me` | Authenticated | — → safe user summary | 401 token, 403 disabled |
| Memberships | `GET /api/auth/me/memberships` | Authenticated | — → mapped GitHub memberships | 401 |

## Repositories and sync

| Purpose | Method and path | Permission | Main request → response | Important errors |
|---|---|---|---|---|
| Analyze | `POST /api/repositories/analyze` | Authenticated | `repository` owner/repo or GitHub URL → repository, created flag, sync, bounded scope | 403 existing MEMBER, 404 GitHub, 422 input, 429/5xx GitHub |
| Create metadata | `POST /api/repositories` | System Admin | owner + repo → repository | 401/403/409/404 |
| List/detail | `GET /api/repositories`, `GET /api/repositories/{id}` | Authenticated | — → role-aware repository data | 401/404 |
| Sync | `POST /api/repositories/{id}/sync` | Repo ADMIN | — → inserted/updated/unchanged counts | 401/403/404/429/5xx |
| Sync history | `GET /api/repositories/{id}/syncs` | Authenticated | optional limit → sync records | 401/404/422 |

## Analytics, RCI and Evidence

| Purpose | Method and path | Permission | Main request → response | Important errors |
|---|---|---|---|---|
| Overview | `GET /api/repositories/{id}/overview` | Authenticated | — → event totals and mapping totals | 401/404 |
| RCI | `GET /api/repositories/{id}/contribution-index` | Authenticated | optional four `weight_*` values → RCI_V1 analysis | 401/404/422 |
| Contributor stats/detail | `GET .../contributor-stats`, `GET .../contributors/{username}` | Authenticated | optional bot filter → activity summary | 401/404 |
| Timelines | `GET .../timeline`, `GET .../contributors/{username}/timeline`, `GET .../members/{member_id}/timeline` | Authenticated | day granularity → points | 401/404/422 |
| Evidence | `GET /api/repositories/{id}/events` | Authenticated | member/author/type, limit, offset → total + stored events | 401/404/422 |
| Unmapped contributors | `GET .../unmapped-contributors` | Repo ADMIN | — → login and event count | 401/403/404 |

RCI requests read SQLite and never trigger GitHub network activity.

## Member Mapping

| Purpose | Method and path | Permission | Main request → response | Errors |
|---|---|---|---|---|
| List mappings | `GET /api/repositories/{id}/members` | Authenticated | — → members and mapped counts | 401/404 |
| Create mapping | `POST /api/repositories/{id}/members` | Repo ADMIN | display name, GitHub username, optional user ID → member + remapped events | 401/403/404/409 |
| Update mapping | `PATCH /api/repositories/{id}/members/{member_id}` | Repo ADMIN | display name and/or username → member + remapped events | 401/403/404/409/422 |

## Repository Access

| Purpose | Method and path | Permission | Main request → response | Errors |
|---|---|---|---|---|
| List access | `GET /api/repositories/{id}/access` | Repo ADMIN | — → all users with effective role/source | 401/403/404 |
| Change role | `PATCH /api/repositories/{id}/access/{user_id}` | Repo ADMIN | `ADMIN` or `MEMBER` → updated access | 401/403/404/409 last admin |

## System Users and diagnostics

| Purpose | Method and path | Permission | Main request → response | Errors |
|---|---|---|---|---|
| Create/list/update user | `POST/GET /api/users`, `PATCH /api/users/{id}` | System Admin | user fields → safe user response | 401/403/404/409/422 |
| GitHub auth status | `GET /api/github/auth-status` | System Admin | — → mode and rate limit, never token | 401/403/429/5xx |
| GitHub diagnostics | `/api/github/{owner}/{repo}/...` | System Admin | bounded diagnostic query → normalized data/warnings | 401/403/404/429/5xx |
| Health | `GET /health` | Public | — → service status | — |

API responses never include password hashes, JWT secrets, verification digests, SMTP passwords or GitHub tokens.
