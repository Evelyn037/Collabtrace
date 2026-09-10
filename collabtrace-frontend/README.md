# CollabTrace Frontend

CollabTrace（协作透镜）前端将 FastAPI Backend 中的真实 GitHub 协作记录呈现为可登录、可分析、可追溯的 Editorial Bento Web 产品。

## Tech Stack

- React 19 + TypeScript + Vite
- React Router
- Axios
- ECharts（Pie / Line 按需加载）
- Lucide React
- Vitest + React Testing Library + jest-dom + user-event
- ESLint + TypeScript ESLint + React Hooks rules

## Install and environment

```powershell
npm ci
Copy-Item .env.example .env
```

默认环境配置：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

前端不持有 GitHub Token、JWT Secret、Verification Secret 或 SMTP credential。所有 GitHub 请求都通过 Backend。

## Run

先启动 Backend，再运行：

```powershell
npm run dev
```

访问 http://localhost:5173 。JWT 仅保存在当前浏览器标签页的 `sessionStorage`；刷新可恢复登录与 Repository 选择，关闭标签页后不会长期保留。

## Build and test

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

`lint` 运行真正的 ESLint；`typecheck` 独立运行 TypeScript compiler checks。单元测试 Mock 前端 API module，不连接真实 Backend、GitHub 或 SMTP。`package-lock.json` 是可复现安装来源，应保留并在 CI/fresh clone 中使用 `npm ci`。

## Routes

- `/auth`：密码登录、邮箱验证码登录、MEMBER 注册
- `/dashboard`：Repository overview、Contributor mountain ranking、timeline
- `/repositories/:repositoryId/contributors/:githubUsername`：Contributor profile、timeline、Contribution Evidence
- `/admin`：仅当前 Repository ADMIN 可访问，固定包含 Repositories、Member Mapping、Access、Sync History 四个 Repository 级标签页
- `/system/users`：仅 System Admin 可访问的系统账号管理页；入口位于右上角 Profile Menu，不属于 Repository 管理中心
- `/403`：权限不足

## Architecture

```text
React UI
  ↓
AuthContext + RepositoryContext
  ↓
Typed Axios API modules
  ↓
FastAPI Backend
  ↓
SQLite + GitHub REST API
```

Dashboard 不包含生产 mock 数据。Contributor 使用 GitHub `author_login` 作为核心身份；Mapping 只增强显示身份，不改变活动数量或排名。Activity Rank 表示活动量，不是贡献评分或绩效评价。

## Repository-scoped permissions

Repository Selector 的每个选项和旁边的克制型徽章都会显示当前账号在该
Repository 中的 `ADMIN` 或 `MEMBER` 角色。切换 Repository 后，Sync、管理中心、
Mapping 与 Access 控件立即按 `selectedRepository.current_user_role` 更新；JWT 中的
global role 不用于判断 repository 管理权限。

所有已登录用户都能使用 Analyze。首次分析尚不存在的 Repository 时，创建者会
自动成为该 Repository ADMIN；输入已经存在但自己只有 MEMBER 权限的 Repository
时，界面提供只读提示和打开 Dashboard 的入口，不触发 refresh。

Access Tab 供当前 Repository ADMIN 查看完整用户目录、提升或降低该 Repository
角色，并显示显式/默认访问状态。这里编辑的是 `RepositoryAccess.role`，只影响当前
Repository；没有显式记录的账号按只读 MEMBER 展示。最后一名管理员不能被降级，
后端返回的 409 会在界面中清晰展示。

系统级权限来自 `User.role`，与 `RepositoryAccess.role` 相互独立。Profile Menu 将
`User.role=ADMIN` 显示为 `SYSTEM ADMIN`，将 `User.role=MEMBER` 显示为
`STANDARD USER`；只有 System Admin 才能进入 `/system/users` 修改系统账号角色与
状态。切换 Repository 不会离开 System Users 页面，也不会改变系统角色。

两个典型权限组合：

- Alice：System Role 为 STANDARD USER，在 Repo A 是 ADMIN、在 Repo B 是 MEMBER。她可以管理 Repo A、只读访问 Repo B，但不能进入 System Users。
- Bob：System Role 为 SYSTEM ADMIN，在 Repo A 是 MEMBER。他可以管理 System Users，但不能进入 Repo A 的管理中心。

## RCI Dashboard

Mountain 使用 `RCI_V1` 的 `rci_rank`，marker 显示 `RCI xx.x% · #rank`。Research
Baseline 与 Custom Weights badge 会标明当前视图；Weights 面板提供四维 slider/number、
归一化预览、apply/reset/cancel。偏好只保存在按 user + repository 隔离的当前
`sessionStorage`，不会修改共享数据。

Quick View 保留 Activity Events/Activity Rank，并新增当前 RCI、RCI Rank、计算模式、
未加权 Contribution Composition 及 Why This RCI 分解。Methodology 面板公开公式、过滤、
robust churn、active dimensions、coverage、同步范围、免责声明与研究参考。Contributor
Detail 继续展示既有 baseline/activity 档案，不继承个人 custom weights。
