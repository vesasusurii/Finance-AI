# Borek Finance — project context

Living notes for agents and developers. Update this file when behaviour, architecture, or handoff state changes.

## Product

- **Name:** Borek Finance (repo: Finance-AI)
- **Purpose:** Purchase invoice OCR/extraction, review queue, bank matching (later), Excel export
- **Stack:** FastAPI + PostgreSQL + React/Vite; OpenAI Vision primary OCR ([DOCS/8. OCR-Technology.md](DOCS/8. OCR-Technology.md))

## Local development

```bash
# From repo root — copy .env from .env.example first
docker compose up -d db backend

docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_admin.py

cd frontend && npm install && npm run dev
```

- **Login:** `finance@borek.com` / `changeme` (after seed)
- **Frontend:** http://localhost:5173 — use **empty** `VITE_API_BASE_URL` in `frontend/.env` so cookies work via Vite proxy
- **API:** http://localhost:8000 — health: `/api/health`
- **Auth:** JWT in `access_token` HttpOnly cookie; `GET /api/auth/me` returns **204** when signed out (not 401)

## OCR / upload pipeline (OpenAI-primary)

Per [DOCS/8. OCR-Technology.md](DOCS/8. OCR-Technology.md), **all invoice OCR is OpenAI** — no Google Document AI or Tesseract in this build.

1. `POST /api/invoices/upload` (multipart `files`)
2. `InvoiceExtractionService`:
   - **Every file** → page images → **OpenAI Vision** (`gpt-4o-mini` by default), `detail: high`
   - **PDFs:** all pages up to `OPENAI_MAX_PDF_PAGES` (25); batched in groups of `OPENAI_VISION_PAGE_BATCH_SIZE` when &gt; 6 pages, then merged; full `pdfplumber` text with page markers as hints
   - **Low confidence / missing fields:** automatic retry with `OPENAI_MODEL_STRONG` (`gpt-4o`)
3. Pydantic validation → `invoices` + audit log (`provider: openai_vision`, `model: …`)
4. Required: `OPENAI_API_KEY` in `.env`

**Not yet implemented:** Google Document AI failover, Tesseract, upload list API, file preview in review UI.

## Frontend (no mock data)

- UI from `exact-screenshot-clone` layout; data from APIs only
- **Live:** Upload, Purchase invoices (documents), OCR review queue, Excel export
- **Placeholder screens:** Bank statements, matching, manual review, admin (empty state copy)

## Key paths

| Area | Path |
|------|------|
| OCR service | `backend/services/invoice_extraction_service.py` |
| PDF helpers | `backend/services/ocr/pdf_reader.py` |
| Upload API | `backend/api/routers/invoice_router.py` |
| Auth | `backend/middleware/auth.py`, `frontend/src/auth/` |
| Branding | `DOCS/BRANDING.md`, `branding/theme.css` |
| Specs | `DOCS/*.md` |

## Session notes (2026-05-22)

- Replaced partial clone integration with full UI; removed `frontend/src/lib/mock-data.ts`
- Fixed OCR: scanned PDFs no longer fail with “could not extract text”; Vision used via `pypdfium2`
- Added root `.gitignore`, this `context.md`
- Docker backend image rebuild required after `requirements.txt` change (`pypdfium2`, `Pillow`)

## Handoff checklist

- [ ] Confirm `OPENAI_API_KEY` set in `.env` (never commit)
- [ ] `docker compose build backend` after pulling OCR dependency changes
- [ ] Restart `npm run dev` after `frontend/.env` changes
- [ ] Test upload: digital PDF + scanned PDF
- [ ] Bank/matching phases per `DOCS/0. Roadmap.md`
