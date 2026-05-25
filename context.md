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

**After Phase 2 pull:** `docker compose build backend` (adds `xlrd` for `.xls` bank files).

## OCR / upload pipeline (OpenAI-primary)

Per [DOCS/8. OCR-Technology.md](DOCS/8. OCR-Technology.md), **all invoice OCR is OpenAI** — no Google Document AI or Tesseract in this build.

1. `POST /api/invoices/upload` (multipart `files`)
2. `InvoiceExtractionService` → OpenAI Vision, audit `openai_vision`
3. Required: `OPENAI_API_KEY` in `.env`

## Bank statement pipeline (Phase 2)

1. `POST /api/bank-statements/upload` (multipart `file`, `.xlsx` / `.xls`)
2. `BankStatementService` → `bank_excel_parser` (header scan for Data + Komenti) → `invoice_number_parser` per comment
3. Tables: `bank_statements`, `bank_transactions` (`reconciliation_status` starts `pending`)
4. `GET /api/bank-statements`, `GET /api/bank-transactions?bank_statement_id=…`

**Not yet:** `POST /api/reconciliation/run` (Phase 3), matching UI

## Frontend (no mock data)

- **Live:** Upload, Purchase invoices, OCR review, Excel export, **Bank statements upload + preview**, **Bank transactions table**
- **Placeholder:** Matching, manual review, admin

| Route | Screen |
|-------|--------|
| `/` | Invoice upload |
| `/documents` | Purchase invoices |
| `/review` | OCR review queue |
| `/bank-statements` | Bank Excel upload + statement list |
| `/bank-transactions` | Parsed transaction rows |
| `/exports` | Excel export |
| `/matching` | Placeholder (Phase 3) |

## Key paths

| Area | Path |
|------|------|
| Bank service | `backend/services/bank_statement_service.py` |
| Excel parser | `backend/utils/bank_excel_parser.py` |
| Invoice # parser | `backend/utils/invoice_number_parser.py` |
| Bank API | `backend/api/routers/bank_statement_router.py` |
| OCR service | `backend/services/invoice_extraction_service.py` |
| Specs | `DOCS/*.md` |

## Session notes

- **2026-05-22:** Phase 1 — full UI, OpenAI Vision OCR, scanned PDFs via `pypdfium2`
- **2026-05-22:** Phase 2 — bank models/migration, Excel parse, bank APIs, `/bank-statements` + `/bank-transactions` UI

## Handoff checklist

- [ ] `docker compose build backend` && `alembic upgrade head`
- [ ] Test bank upload with ProCredit-style `.xlsx` or `.xls`
- [ ] Confirm `OPENAI_API_KEY` for invoice OCR tests
- [ ] Phase 3 matching per `DOCS/0. Roadmap.md`
