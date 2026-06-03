# Outlook → Borek Finance invoice ingestion (n8n)

Production workflow: **`workflows/outlook-invoice-ingest.json`**

## Architecture (important)

n8n is **orchestration only**. It does **not** run OCR, OpenAI, or direct Supabase inserts.

| Step | Where it runs |
|------|----------------|
| Read Outlook email + attachments | n8n |
| Upload file + email metadata | `POST /api/invoices/email-upload` |
| Store file (Supabase Storage or local) | FastAPI backend |
| OCR + extraction + `invoices` row | Backend worker (Redis/RQ) |
| View in dashboard | React `/documents` |

Do **not** add separate Supabase Insert nodes unless you want duplicate data. The backend already writes to PostgreSQL (Supabase) and storage bucket (`SUPABASE_STORAGE_BUCKET`, default `invoices`).

## Backend setup

1. Add to `.env`:

```env
EMAIL_INGEST_API_KEY=your-long-random-secret
EMAIL_INGEST_USER_EMAIL=finance@borek.com
```

2. Ensure `EMAIL_INGEST_USER_EMAIL` exists and is active in the `users` table.

3. Restart API + worker:

```bash
docker compose restart backend worker
```

4. Test the endpoint:

**PowerShell** (use `curl.exe` or the helper script — plain `curl` is an alias and will fail):

```powershell
# Option A — helper script (from repo root)
$env:EMAIL_INGEST_API_KEY = "your-key-from-env"
.\scripts\test-email-upload.ps1 -FilePath "C:\path\to\invoice.pdf"

# Option B — real curl (note curl.exe and backtick line breaks)
curl.exe -X POST "http://localhost:8000/api/invoices/email-upload" `
  -H "X-Email-Ingest-Key: your-key-from-env" `
  -F "file=@C:\path\to\invoice.pdf" `
  -F "source=outlook_email" `
  -F "sender_email=vendor@example.com" `
  -F "message_id=test-msg-001" `
  -F "attachment_name=invoice.pdf"
```

**bash / Git Bash:**

```bash
curl -X POST "http://localhost:8000/api/invoices/email-upload" \
  -H "X-Email-Ingest-Key: YOUR_KEY" \
  -F "file=@invoice.pdf" \
  -F "source=outlook_email" \
  -F "sender_email=vendor@example.com" \
  -F "message_id=test-msg-001" \
  -F "attachment_name=invoice.pdf"
```

Expected: **202** JSON with `"status": "queued"` (OCR runs asynchronously).

## n8n environment variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `FINANCE_API_URL` | `http://host.docker.internal:8000` | API base (see networking below) |
| `EMAIL_INGEST_API_KEY` | same as backend `.env` | Header `X-Email-Ingest-Key` |
| `OUTLOOK_FOLDER` | `Inbox` or `Invoices` | Mailbox folder to watch |

### Networking

| n8n runs on | Use `FINANCE_API_URL` |
|-------------|------------------------|
| Same machine as API | `http://localhost:8000` |
| Docker (API on host) | `http://host.docker.internal:8000` |
| Docker Compose same stack | `http://backend:8000` |
| n8n Cloud | Public HTTPS URL to your API (not `localhost`) |

## Fix: HTTP 400 on “Send to AI Backend”

Common causes:

| Problem | Fix |
|---------|-----|
| Endpoint missing (old build) | Deploy backend with `/api/invoices/email-upload` |
| Wrong field name | Multipart field must be **`file`** (singular), not `files` |
| JSON body instead of multipart | Use **Form-Data** / **multipart-form-data** |
| No binary attached | Map attachment binary to `file` (`inputDataFieldName`: `data`) |
| Missing API key | Header **`X-Email-Ingest-Key`** (not session cookie) |
| Unsupported type | PDF, PNG, JPG, JPEG only |
| `localhost` from Docker n8n | Use `host.docker.internal` or service name |

### Correct HTTP Request node (n8n)

- **Method:** POST  
- **URL:** `{{ $env.FINANCE_API_URL }}/api/invoices/email-upload`  
- **Authentication:** None (use header below)  
- **Header:** `X-Email-Ingest-Key` = `{{ $env.EMAIL_INGEST_API_KEY }}`  
- **Body content type:** Form-Data  
- **Body parameters:**

| Name | Type | Value |
|------|------|--------|
| `file` | Binary | binary property `data` from attachment node |
| `source` | Text | `outlook_email` |
| `sender_email` | Text | from email |
| `sender_name` | Text | from email |
| `email_subject` | Text | subject |
| `message_id` | Text | Outlook message id |
| `attachment_name` | Text | filename |

## Import workflow

1. n8n → **Workflows** → **Import from file**  
2. Select `n8n/workflows/outlook-invoice-ingest.json`  
3. Configure **Microsoft Outlook OAuth2** credential  
4. Set environment variables  
5. Activate workflow  

## Duplicate detection

| Layer | Behaviour |
|-------|-----------|
| Same file hash | `status: duplicate`, `duplicate: true` (linked to existing upload) |
| Same invoice after OCR | Backend review tasks / matching rules |
| n8n | Logs `duplicate_detected` branch; no second API upload needed |

Business-key duplicate (invoice number + supplier + amount) is enforced in the backend after extraction, not in n8n.

## Logging events

The workflow emits structured log objects (`event` field) for:

`workflow_start` · `email_received` · `attachment_processed` · `backend_success` · `backend_failure` · `duplicate_detected` · `unsupported_file` · `workflow_complete`

Connect the **Log event** branch to Slack, email, or a logging workflow as needed.
