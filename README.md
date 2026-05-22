# Finance-AI

AI-powered internal tool for **Borek Finance**: purchase invoice extraction and bank statement matching.

## Branding

All UI work must follow the Borek design system:

- **[DOCS/BRANDING.md](DOCS/BRANDING.md)** — voice, colours, typography, component rules
- **[branding/theme.css](branding/theme.css)** — CSS tokens and ready-made classes

## Documentation

See [`DOCS/1. Project Summary.md`](DOCS/1.%20Project%20Summary.md) for scope and the full document map.

Agent handoff and session notes: [`context.md`](context.md).

Implementation roadmap (phase-by-phase, file-by-file): [`DOCS/0. Roadmap.md`](DOCS/0.%20Roadmap.md)

Technical architecture and workflows: [`DOCS/README.md`](DOCS/README.md)

## Quick start (Docker — team default)

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and JWT_SECRET

docker compose up -d --build
curl http://localhost:8000/api/health
```

Details: [`DOCS/12. Deployment & Environments.md`](DOCS/12.%20Deployment%20%26%20Environments.md)

Frontend (after Phase 0 scaffold):

```bash
docker compose --profile full up -d --build
```

Migrations:

```bash
docker compose exec backend alembic upgrade head
```

## Repository layout

```
backend/     FastAPI — auth, invoices, export (Phase 1)
frontend/    React + Vite — dashboard, upload, table, export
branding/    theme.css (import as @brand in frontend)
DOCS/        Specifications
docker-compose.yml
.env.example
```

**Seed login (local):** after `python scripts/seed_admin.py` → `finance@borek.com` / `changeme`
