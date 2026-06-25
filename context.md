# Borek Finance — project context

Living notes for agents and developers. Update this file when behaviour, architecture, or handoff state changes.

## Product

- **Name:** Borek Finance (repo: Finance-AI)
- **Purpose:** Purchase invoice OCR/extraction, review queue, bank matching, Excel export
- **Stack:** FastAPI + PostgreSQL + React/Vite; OpenAI Vision primary OCR ([DOCS/8. OCR-Technology.md](DOCS/8. OCR-Technology.md))

## Local development

```bash
# From repo root — copy .env from .env.example first
docker compose build backend
docker compose up -d db backend

docker compose exec backend alembic upgrade head

cd frontend && npm install && npm run dev
```

- **Login:** use an existing account — create users at **Admin → Users** when signed in as admin
- **Frontend:** http://localhost:5173 — use **empty** `VITE_API_BASE_URL` in `frontend/.env` so cookies work via Vite proxy
- **API:** http://localhost:8000 — health: `/api/health`
- **Auth:** JWT in `access_token` HttpOnly cookie; `GET /api/auth/me` returns **204** when signed out (not 401)

## OCR / upload pipeline (OpenAI Vision only)

Per [DOCS/8. OCR-Technology.md](DOCS/8. OCR-Technology.md), **all invoice scanning is OpenAI Vision** — PDF, JPEG, JPG, PNG only. No pdfplumber text OCR, Google Document AI, or Tesseract.

1. `POST /api/invoices/upload` (multipart `files`) — PDF, JPEG, JPG, PNG
2. **Digital PDFs:** text-layer hints or text-only LLM first (`OPENAI_TEXT_FIRST_*`); falls back to Vision when incomplete
3. PDFs (Vision path): pages rasterised with `pypdfium2` → JPEG → OpenAI Vision (`gpt-4o-mini`, optional retry `gpt-4o`)
4. Images: sent directly to OpenAI Vision
5. Audit provider: `openai_vision` or `text_hints` / `text_llm` — requires `OPENAI_API_KEY` in `.env` for LLM paths

## Bank statement pipeline (Phase 2)

1. `POST /api/bank-statements/upload` (multipart `file`, `.xlsx` / `.xls`)
2. `BankStatementService` → `bank_excel_parser` (header scan for Data + Komenti) → `invoice_number_parser` per comment
3. Tables: `bank_statements`, `bank_transactions` (`reconciliation_status` starts `pending`)
4. `GET /api/bank-statements`, `GET /api/bank-transactions?bank_statement_id=…`

## Reconciliation (Phase 3)

1. `POST /api/reconciliation/run` — optional `{ "bank_statement_id": N }`
2. Sets `paid_at_date` on matched invoices; creates `invoice_payment_matches` + `review_tasks`
3. `GET /api/reconciliation/results`, `POST /api/reconciliation/approve-match`, `POST /api/reconciliation/reject-match`
4. `GET /api/review` — open review tasks (`bank_match`)

## Bank comment extraction — hybrid regex + LLM (Phase 3 hardening)

Invoice numbers come out of the `Komenti` / `Comment` column in two tiers:

1. **Tier 1 — hardened regex** (`backend/utils/invoice_number_parser.py`):
   - Four ranked patterns: keyword-anchored → slash-serial → dashed serial → bare numeric
   - Chained-keyword absorption (`Pagese per fat. FDP25-…`, `Pagesa fature 1/2026/…`)
   - Multi-invoice split on `,`, `;`, ` dhe `, ` and `, ` & `, ` + `
   - Position-tracking dedupe: substring matches of an already-captured token are skipped (no more `00114712` leaking out of `FDP25-00114712`)
   - Explicit blocklists for IBANs, bank account numbers (>=13 digits), card approval/auth codes (`APROVAL:`, `TERM:`, `RRN:`), date fragments (`02/2026`), 4-digit years
   - Runs at upload time to populate the preview and at matching time as the first pass

2. **Tier 2 — LLM disambiguation** (`backend/services/bank_comment_extraction_service.py`):
   - Gated by `needs_llm_fallback(comment, regex_candidates)` — only fires when regex returned nothing for a keyworded comment, returned >3 candidates, or returned short bare numerics with no keyword anchor
   - Batched `gpt-4o-mini` JSON call (default 25 comments / call, `temperature=0`)
   - Wired in `MatchingService.run()` as a pre-pass: collects distinct ambiguous comments → single batched call → results merged via `merge_candidates()` before the per-txn matching loop
   - All LLM output flows through the same `normalize_invoice_number` + `is_tax_or_client_id` filters as regex, so DB keys stay consistent
   - Optional: returns `None` from DI when `BANK_COMMENT_USE_LLM=false` or `OPENAI_API_KEY` is missing → matching falls back to regex-only

Tuning env vars: `BANK_COMMENT_USE_LLM`, `BANK_COMMENT_LLM_MODEL`, `BANK_COMMENT_LLM_BATCH_SIZE`, `BANK_COMMENT_LLM_TIMEOUT_SECONDS`, `BANK_COMMENT_LLM_MAX_RETRIES` (see `.env.example`). Test suite `backend/tests/test_invoice_number_parser.py` locks in the real-world false-positive cases (IBAN/account/approval/date) — keep adding rows as new banks ship new formats.

## Frontend (no mock data)

| Route | Screen |
|-------|--------|
| `/` | Invoice upload |
| `/documents` | Purchase invoices — **edit, save, delete** in detail drawer |
| `/review` | Redirect → `/manual-review` (legacy alias) |
| `/manual-review` | Manual review queue (`review_tasks`) |
| `/bank-statements` | Bank Excel upload + statement list → link to matching |
| `/bank-transactions` | Parsed transaction rows |
| `/matching` | Run matching + tabbed results (approve / reject) |
| `/exports` | Excel export |
| `/admin/users` | User management + bank statement counts |
| `/admin/permissions` | Role capabilities |
| `/admin/audit-logs` | Audit log viewer |
| `/admin/settings` | System settings |

## Key paths

| Area | Path |
|------|------|
| OCR service | `backend/services/invoice_extraction_service.py` |
| Text-first OCR | `backend/services/text_first_extraction_service.py` |
| Bank service | `backend/services/bank_statement_service.py` |
| Excel parser | `backend/utils/bank_excel_parser.py` |
| Invoice # parser (regex tier 1) | `backend/utils/invoice_number_parser.py` |
| Bank comment LLM (tier 2) | `backend/services/bank_comment_extraction_service.py` |
| Matching service | `backend/services/matching_service.py` |
| Bank API | `backend/api/routers/bank_statement_router.py` |
| Reconciliation API | `backend/api/routers/reconciliation_router.py` |
| Documents UI | `frontend/src/routes/documents.tsx` |
| Matching UI | `frontend/src/routes/matching.tsx` |
| Specs | `DOCS/*.md` (see `DOCS/0. Roadmap.md`) |
| Phase A runbook (n8n + Documents) | `DOCS/PHASE_A_STABILISATION.md` |
| Finance sign-off items | `DOCS/FINANCE_PENDING_DECISIONS.md` |

## Session notes

- **2026-05-29:** Invoice upload dedupe by file hash (`uploaded_files.content_sha256`, partial unique index for `file_kind=invoice`). Duplicate upload does not re-run OCR or create a second `invoices` row; `invoice_access` grants the second user visibility. Original `uploaded_by` on the invoice is unchanged. Upload API returns `processing_status=linked` with `message` and `original_uploader_email`. Failed prior upload of the same hash is re-processed in place.
- **2026-05-22:** Phase 1 — full UI, OpenAI Vision OCR, scanned PDFs via `pypdfium2`
- **2026-05-22:** Phase 2 — bank models/migration, Excel parse, bank APIs, `/bank-statements` + `/bank-transactions` UI
- **2026-05-22:** Phase 3 — matching service, reconciliation + review APIs, documents drawer edit/save/delete, `/matching` UI
- **2026-05-25:** Bank comment extraction hardened — position-tracking dedupe, IBAN/account/approval blocklists, chained-keyword absorption; added `BankCommentExtractionService` (batched `gpt-4o-mini`) as LLM fallback wired into `MatchingService.run()` pre-pass; 20 tests cover the real-world false-positive cases
- **2026-05-26:** Matching crash fix — `POST /api/reconciliation/run` was 500-ing with `sqlalchemy.exc.MultipleResultsFound` when two `invoices` rows shared the same `invoice_number_normalized` (no UNIQUE constraint on that column). Fixed in three layers:
  1. `InvoiceRepository.find_by_number` now returns `(invoice, ambiguous)`: 0 rows → `(None, False)`, 1 row → `(row, False)`, 2+ rows → `(None, True)` + warning log (no more `MultipleResultsFound`). Added `list_by_number` helper.
  2. `MatchingService.run` wraps each transaction in `try/except` and delegates to a new `_process_txn`; failed rows become `needs_review` with a `internal_error` review task so one bad txn can no longer abort the whole run.
  3. Ambiguous lookups produce a new `duplicate_invoice_in_db` review task (existing `create_bank_unmatched` signature — no schema change). Per-txn dedupe by `invoice_id` guards against the `(invoice_id, bank_transaction_id)` unique constraint when two candidates resolve to the same invoice.
  - Frontend `/matching` now renders all relevant review reasons (`no_invoice_in_db`, `duplicate_invoice_in_db`, `internal_error`, `no_invoice_numbers_detected`, `missing_transaction_date`) with a `StatusBadge` and the `reviewReasonLabel()` helper in `frontend/src/lib/labels.ts`.
  - Data clean-up still required: list duplicates via `docker compose exec backend python scripts/list_duplicate_invoice_numbers.py` and delete / rename offenders from the documents page. Migration `r5s6t7u8v9w0` adds a partial unique index on `(uploaded_by, invoice_number_normalized)` when no duplicates remain; new saves return HTTP 409 `duplicate_invoice_number`.
- **2026-05-26:** Bank Excel `transaction_date` parsing fix — every row of statement #3 had `transaction_date = NULL`, so `MatchingService` skipped them with `missing_transaction_date` and invoice `613260192` (correctly detected, present in DB) never matched. `utils/bank_excel_parser._parse_date` only knew three string formats and dropped Excel serial numbers / unknown shapes to `None` silently. Fixed in four layers:
  1. `_parse_date` now also accepts Excel serial floats/ints (`days since 1899-12-30`, range-guarded), dashed (`25-02-2026`), 2-digit-year (`25.02.26`), ISO with time (`2026-02-25T12:30:45`), and date+time (`25.02.2026 12:30:45`) strings. Falls back to a head-split for trailing-junk (`"25.02.2026 Mo"`). Logs a `WARNING` with the raw value when it gives up — surprises are now visible in `docker compose logs backend` instead of vanishing as silent `NULL`s.
  2. `_load_rows_xls` now converts xlrd `XL_CELL_DATE` cells via `xldate_as_datetime(value, book.datemode)` so legacy `.xls` exports stop returning dates as raw floats.
  3. `REQUIRED_HEADERS` gained German tokens — `datum` (matches `Buchungsdatum` / `Valutadatum` via substring), `valuta`, `verwendungszweck`, `beschreibung`, `betreff`, `purpose` — so Kreissparkasse-style exports parse the right columns.
  4. `BankStatementUploadResponse.unparsed_date_rows` (Pydantic + TS) is surfaced as a yellow alert on `/bank-statements` after upload: "N of M rows have an unparsable date and will be skipped by matching" with the accepted formats spelled out. Backend also logs the count.
  - Tests in `backend/tests/test_bank_excel_parser.py` cover every accepted shape + defensive rejection of bool/0/negative/huge-serial/garbage strings (verified via direct module invocation since pytest isn't in the backend image).
  - Existing broken rows: `POST /api/bank-statements/{id}/reparse` re-reads the stored Excel and updates transaction dates without re-upload. Resolves `missing_transaction_date` review tasks when dates are fixed.

## Handoff checklist

- [ ] `docker compose build backend` && `alembic upgrade head` (includes `b2c3d4e5f6a7_add_match_review_tables`)
- [ ] Confirm `OPENAI_API_KEY` for invoice OCR tests
- [ ] Upload invoices + bank statement, then **Run Matching** on `/matching`
- [ ] Test documents drawer Save and Delete
- [x] Phase 4 manual review queue per `DOCS/0. Roadmap.md`
