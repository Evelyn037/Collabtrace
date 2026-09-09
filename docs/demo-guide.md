# Demo Guide

Target: a short, evidence-led walkthrough. Prepare local accounts and an already synchronized repository before presenting; never store passwords in project files.

## Three-window defense layout

- **Left 60% — Frontend:** `http://localhost:5173`
- **Right top 40% — Backend console:** `python -m uvicorn app.main:app --reload`
- **Right bottom 40% — Swagger or persisted state:** `http://127.0.0.1:8000/docs`, Sync History, or a read-only database viewer

Keep the backend console visible so the audience can correlate a frontend action with real `[FLOW]` stages. Never display `.env`, authorization headers, credentials, password hashes or verification-code records.

## Path A — Live data loop

Login → Dashboard → Analyze a moderate public repository → observe Analyze/Fetch/Normalization/Persistence FLOW logs → show inserted/updated/unchanged counts → return to Dashboard → RCI → Contributor Detail → Evidence → original GitHub URL.

Narrate the real path:

```text
User Input → React → HTTP → FastAPI → GitHub REST API → Normalize → SQLite
→ Analytics / RCI → JSON → React → Evidence → original GitHub record
```

## Main flow

1. Log in with a locally prepared Standard User.
2. Paste a moderate public GitHub `owner/repo` into **分析 Repository**.
3. Show loading, successful sync and that the creator is Repo ADMIN.
4. Open **情况总览** and explain RCI as a team-relative index.
5. Point out Top 4 mountain markers: Gold #1, Silver #2, Bronze #3, no medal for #4.
6. Open **Weights**, change the dimension emphasis and apply it.
7. Show Custom Weights, updated RCI/ranking/medals, then open a Contributor Quick View.
8. Explain that Contribution Composition stays unchanged because it is unweighted.
9. Open **Why This RCI** and show dimension score, effective weight, weighted contribution and final RCI.
10. Open the Contributor Detail page and filter Contribution Evidence.
11. Use **View on GitHub** to open a real original record.
12. Switch the same user between an ADMIN repository and a MEMBER repository: Sync/Admin Center appear only for ADMIN.
13. If needed, use a System Admin to show that System Users is separate from Repository Admin Center.

## Path B — Offline fallback

If GitHub is unavailable or rate-limited, do not pretend Live Analyze succeeded. Select the prepared `fastapi/fastapi` repository and demonstrate Dashboard, RCI, Custom Weights, Quick View and Evidence from SQLite.

Also show Sync History and explain the resilience boundary accurately: GitHub is currently unavailable, but previously synchronized records remain in SQLite, so local analytics and evidence views continue working. This is persisted-data resilience, not a claim that a failed live sync succeeded.

## Live Analyze warning

Live Analyze depends on network access, GitHub API availability and PAT rate limit. Avoid very large repositories in the live portion because the bounded sync may still take tens of seconds. The UI reports a bounded analysis scope; do not describe it as complete GitHub history.

## Pre-demo checklist

- Backend `/health` and frontend load successfully.
- One System Admin and one Standard User are active.
- The Standard User is ADMIN on one repository and MEMBER on another.
- A synchronized repository has at least four contributors and real Evidence URLs.
- GitHub auth status has adequate remaining rate limit without exposing the token.
- Keep the backend console available if using console verification codes.
