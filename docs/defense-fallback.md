# Defense Fallback

The local demonstration remains independent of Render and Neon. It uses the existing React frontend, FastAPI backend, and `collabtrace-backend/data/collabtrace.db`; Phase 5 does not migrate, replace, or upload that database.

## Before the defense

Five minutes before presenting:

1. Open the public CollabTrace site.
2. Log in and open a repository Dashboard to wake the Render backend.
3. Confirm `/health` returns `status: ok`.
4. Keep the local backend and frontend terminals ready as the fallback.

Render Free Web Services may sleep after 15 minutes without inbound traffic. The first request after sleep can take tens of seconds to about one minute. This is a free-hosting limitation, not evidence that CollabTrace data was lost; public data remains in Neon PostgreSQL.

## Start the local fallback

Do not set a process-level production `DATABASE_URL`. The backend `.env` should retain its existing local SQLite value.

```powershell
cd collabtrace-backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd collabtrace-frontend
npm run dev
```

Open `http://localhost:5173`, sign in with a prepared local password account, and verify Dashboard, RCI, Contributor Detail, Evidence, and an original GitHub link. Keep an already synchronized repository available so the fallback does not depend on live GitHub availability.

## Safety checks

- Never delete, reset, rename, or upload `data/collabtrace.db` during fallback preparation.
- Do not copy the Neon connection string into the local frontend or committed files.
- Local `.env`, `.venv`, `node_modules`, databases, and backups remain ignored runtime assets.
- Public and local accounts are separate unless an operator deliberately creates matching records in both databases.
