# Finance-AI

AI-powered internal tool for **Borek Finance**: purchase invoice extraction and bank statement matching.

## Branding

All UI work must follow the Borek design system:

- **[DOCS/BRANDING.md](DOCS/BRANDING.md)** — voice, colours, typography, component rules
- **[branding/theme.css](branding/theme.css)** — CSS tokens and ready-made classes

## Documentation

See [`DOCS/1. Project Summary.md`](DOCS/1.%20Project%20Summary.md) for scope and the full document map.

Implementation roadmap (phase-by-phase, file-by-file): [`DOCS/0. Roadmap.md`](DOCS/0.%20Roadmap.md)

Technical architecture and workflows: [`DOCS/README.md`](DOCS/README.md)

## Quick start (Docker — team default)

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and JWT_SECRET

docker compose up -d --build
curl http://localhost:8000/api/health
```

Details: [`DOCS/12. Deployment & Environments 1.md`](DOCS/12.%20Deployment%20%26%20Environments%201.md)

## Repository layout (starter)

```
backend/     FastAPI — health stub now; full app per DOCS/6
frontend/    React + Vite — scaffold later; Docker profile `full`
DOCS/        Specifications
docker-compose.yml
.env.example
```
