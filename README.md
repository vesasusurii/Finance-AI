# Finance-AI

AI-powered internal tool for **Borek Finance**: purchase invoice extraction and bank statement matching.

## Branding

All UI work must follow the Borek design system:

- **[DOCS/BRANDING.md](DOCS/BRANDING.md)** — voice, colours, typography, component rules
- **[DOCS/branding/theme.css](DOCS/branding/theme.css)** — CSS tokens and ready-made classes

## Documentation

See [`DOCS/1. Project Summary.md`](DOCS/1.%20Project%20Summary.md) for scope and the full document map.

Agent handoff and session notes: [`context.md`](context.md).

Implementation roadmap (phase-by-phase, file-by-file): [`DOCS/0. Roadmap.md`](DOCS/0.%20Roadmap.md)

Technical architecture and workflows: [`DOCS/README.md`](DOCS/README.md)

## Quick start (Docker — team default)

Run all commands from the **repo root** (`Finance-AI/`), not from `backend/`.

```bash
cp .env.example .env
# Edit .env: POSTGRES_PASSWORD, JWT_SECRET, OPENAI_API_KEY

docker compose --profile full up -d --build
docker compose exec backend alembic upgrade head
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API health | http://localhost:8000/api/health |

**Login:** use an existing account in the database. New users are created by an admin at **Admin → Users** (`/admin/users`).

Access tokens refresh every minute (configurable via `JWT_ACCESS_EXPIRE_MINUTES`).

Details: [`DOCS/12. Deployment & Environments.md`](DOCS/12.%20Deployment%20%26%20Environments.md)

### Local frontend only (no Docker UI)

```bash
cd frontend
npm install
npm run dev
```

Requires backend + db running (`docker compose up -d db backend`). Leave `VITE_API_BASE_URL` unset so Vite proxies `/api` to port 8000.

### Common issues

| Symptom | Fix |
|---|---|
| `docker API ... dockerDesktopLinuxEngine` | Start **Docker Desktop**, wait until running, retry compose |
| `OPENAI_API_KEY is not set` | Set key in `.env`, then `docker compose up -d --force-recreate backend` |
| `npm run dev` at repo root fails | No root `package.json` — use `frontend/` or Docker profile `full` |
| API unreachable from UI in Docker | Use default compose frontend env (proxy via `/api`, not direct `:8000`) |
| Restore invoices without re-OCR | `docker compose cp backup_before_rebuild.sql backend:/tmp/backup.sql` then `docker compose exec backend python scripts/restore_invoices_from_backup.py /tmp/backup.sql` |

## Repository layout

```
backend/     FastAPI — auth, invoices, export, bank statements (Phase 1–2)
frontend/    React + Vite — dashboard, upload, table, export
DOCS/branding/    theme.css (import as @brand in frontend)
DOCS/        Specifications
docker-compose.yml
.env.example
```

Users are managed in the app (**Admin → Users**) or persist in the database across restarts.
