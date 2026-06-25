# Phase A — Stabilise n8n ingest and Documents (team runbook)

**Goal (1–2 days):** Outlook → n8n → API → OCR → **Documents** tabs work reliably for Finance daily use.

**Out of scope for Phase A:** Monthly report PDF vs Excel, currency column in the official 12-column export, legacy master Excel import. Those need Finance sign-off — see [FINANCE_PENDING_DECISIONS.md](./FINANCE_PENDING_DECISIONS.md).

---

## Engineering status (repo)

| Area | Status | Notes |
|------|--------|--------|
| `POST /api/invoices/email-upload` | Done | Multipart `file`, header `X-Email-Ingest-Key` |
| `upload_source` + email metadata on `uploaded_files` | Done | Migrations `p3q4r5s6t7u8`, `q4r5s6t7u8v9`; backfill from `audit_logs` |
| Documents tabs (All / Email ingest / Needs review / Unmatched) | Done | `?tab=email-ingest` filters `upload_source=outlook_email` |
| Email ingest columns (sender, subject) | Done | Email ingest tab only |
| n8n Cloud free tier (no `$vars`) | Done | `n8n/workflows/outlook-invoice-ingest.json` + Header Auth |
| Docker n8n | Done | `outlook-invoice-ingest-docker.json`, profile `n8n` |
| ngrok dev tunnel | Done | `scripts/start-ngrok-tunnel.ps1`, compose profile `tunnel` |
| Alembic chain through `r5s6t7u8v9w0` | Done | Includes optional unique index on invoice number per owner |
| Backend startup (`get_review_repo` order) | Fixed | Required for any API call including `/api/auth/me` |

---

## Prerequisites (once per environment)

1. Copy `.env` from `.env.example` and set at minimum:

```env
EMAIL_INGEST_API_KEY=<long-random-secret>
EMAIL_INGEST_USER_EMAIL=<finance-user@your-domain>
OPENAI_API_KEY=<for OCR worker>
```

2. Apply migrations and ensure stack is up:

```powershell
docker compose up -d db redis backend worker frontend
docker compose exec backend alembic upgrade head
```

3. Confirm the ingest user exists in the database (same email as `EMAIL_INGEST_USER_EMAIL`). Create it via **Admin → Users** if needed.

4. Restart after `.env` changes:

```powershell
docker compose restart backend worker
```

Full n8n wiring: [../n8n/README.md](../n8n/README.md).

---

## Phase A test plan (team checklist)

### A1 — API smoke test (no n8n)

```powershell
$env:EMAIL_INGEST_API_KEY = "<from .env>"
.\scripts\test-email-upload.ps1 -FilePath "C:\path\to\sample.pdf"
```

- [ ] HTTP **202**, body contains `"status": "queued"` or `"processing"`
- [ ] After ~30–60 s, invoice appears under **Documents → All**
- [ ] **Documents → Email ingest** shows the row with **Source: Email** and sender/subject if metadata was sent

### A2 — Documents tabs

- [ ] **All** — lists invoices; search and sort work
- [ ] **Email ingest** — only `outlook_email` uploads; empty state if none yet
- [ ] **Needs review** — `review_status=needs_review`
- [ ] **Unmatched** — `match_status=unmatched`
- [ ] Tab counts on badges match list totals (approximate while OCR is running)
- [ ] Excel download on Documents respects active tab filters

### A3 — n8n Cloud (dev with ngrok)

1. [ ] `.\scripts\start-ngrok-tunnel.ps1` — copy HTTPS URL
2. [ ] n8n: Header Auth credential `Borek Finance email ingest` (`X-Email-Ingest-Key`)
3. [ ] n8n: **Send to AI Backend** URL = `https://<ngrok-host>/api/invoices/email-upload`
4. [ ] Send test email with PDF attachment to monitored inbox
5. [ ] n8n execution: HTTP **202** on upload node
6. [ ] Documents → **Email ingest** shows new row

### A4 — Historical rows (if you ingested before metadata migration)

```powershell
docker compose exec backend python scripts/backfill_email_ingest.py
```

- [ ] Old email uploads show **Email** source and sender/subject where audit log exists

### A5 — Data quality guardrails

```powershell
docker compose exec backend python scripts/list_duplicate_invoice_numbers.py
```

- [ ] No duplicate groups **or** duplicates resolved in Documents before relying on matching
- [ ] Bank statements with missing dates: **Re-parse** on `/bank-statements` (no re-upload)

---

## Known limitations (not Phase A blockers)

| Topic | Behaviour |
|-------|-----------|
| ngrok URL | Changes on restart — update n8n HTTP node URL |
| n8n Cloud free tier | No `$vars`; hardcode URL + Header Auth credential |
| Production ingest | Needs fixed HTTPS API host (not ngrok); see n8n README |
| Duplicate invoice numbers | App blocks new duplicates (409); clean existing via script |
| Official Excel export | **12 columns** only; `currency` stays in DB until Finance approves column |

---

## When Phase A is “done”

- [ ] Finance user can email an invoice PDF and see it in **Email ingest** within one OCR cycle
- [ ] Portal upload still works on **Upload** and appears under **All**
- [ ] No recurring 500s on login (`/api/auth/me`) or `/api/invoices`
- [ ] n8n runbook assigned (who updates ngrok URL, who owns Outlook credential)

Then proceed to **Phase B** (matching / partial pay — largely implemented) or **Finance decisions** in [FINANCE_PENDING_DECISIONS.md](./FINANCE_PENDING_DECISIONS.md).

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [n8n/README.md](../n8n/README.md) | Workflows, Cloud vs Docker, troubleshooting |
| [10. Excel-File-Formats.md](./10. Excel-File-Formats.md) | 12-column export spec, pending columns |
| [context.md](../context.md) | Living handoff notes |
