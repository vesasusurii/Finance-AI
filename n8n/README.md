# Outlook → Borek Finance invoice ingestion (n8n)

> **Security:** The ngrok tunnel profile is for **local development only**. Never expose the API publicly without a strong `EMAIL_INGEST_API_KEY`, HTTPS, and network restrictions. Prefer VPN or private networking in production.

Production workflow: **`workflows/outlook-invoice-ingest.json`** (n8n Cloud free tier)

| Workflow file | Use when |
|---------------|----------|
| `outlook-invoice-ingest.json` | n8n Cloud — hardcoded ngrok URL + Header Auth credential (no `$vars`) |
| `outlook-invoice-ingest-docker.json` | Self-hosted n8n in Docker Compose — `http://backend:8000` |

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

## n8n Cloud + ngrok (recommended for Cloud workflows)

n8n Cloud cannot reach `localhost`. Use **ngrok** to expose your local API over HTTPS.

### 1. Get an ngrok authtoken

1. Sign up at [ngrok.com](https://ngrok.com) (free tier works)
2. Copy your token from [dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Add to `.env`:

```env
NGROK_AUTHTOKEN=your_token_here
```

### 2. Start the tunnel

From the repo root:

```powershell
.\scripts\start-ngrok-tunnel.ps1
```

This starts the backend (if needed), runs ngrok in Docker, and prints your public HTTPS URL.

Inspect traffic at **http://localhost:4040**.

Manual start:

```powershell
docker compose --profile tunnel up -d
```

### 3. Configure n8n Cloud

**If `$vars.FINANCE_API_URL` shows `[undefined]`:** Custom Variables need **Pro Cloud** (or Enterprise). On **Starter / free Cloud**, use the workaround below instead of `$vars` or `$env`.

#### Option A — Pro Cloud (Variables)

**Settings → Variables** (exact names, case-sensitive):

| Name | Value |
|------|--------|
| `FINANCE_API_URL` | `https://xxxx.ngrok-free.app` (no trailing slash) |
| `EMAIL_INGEST_API_KEY` | Same as `.env` |

**Send to AI Backend:**

- URL: `={{ $vars.FINANCE_API_URL }}/api/invoices/email-upload`
- Header `X-Email-Ingest-Key`: `={{ $vars.EMAIL_INGEST_API_KEY }}`
- Header `ngrok-skip-browser-warning`: `true`

#### Option B — Starter / free Cloud (no Variables)

Do **not** use `$vars` or `$env`. Hardcode the URL and store the API key in a **Credential**.

1. **Credentials → Add credential → Header Auth**
   - Name: `X-Email-Ingest-Key`
   - Value: your `EMAIL_INGEST_API_KEY` from `.env`
   - Save as e.g. `Borek Finance email ingest`

2. **Send to AI Backend** node:
   - **Method:** POST
   - **URL:** paste the full ngrok URL (no `{{ }}`):
     ```
     https://YOUR-NGROK-URL.ngrok-free.app/api/invoices/email-upload
     ```
   - **Authentication:** Generic Credential Type → **Header Auth** → select the credential above
   - **Send Headers:** add one more header:
     - `ngrok-skip-browser-warning` = `true`
   - **Body:** Form-Data, field `file` = binary attachment, plus `source`, `sender_email`, `message_id`, `attachment_name`, etc.

When ngrok restarts and the URL changes, update the **URL field** in this node (re-run `.\scripts\start-ngrok-tunnel.ps1` for the new URL).

### 4. Test through the tunnel

```powershell
# Replace with your ngrok URL from the script
curl.exe https://YOUR-NGROK-URL.ngrok-free.app/api/health

# Full email-upload test
.\scripts\test-email-upload.ps1 -ApiUrl "https://YOUR-NGROK-URL.ngrok-free.app/api/invoices/email-upload" -FilePath "C:\path\to\invoice.pdf"
```

Expected: health → `{"status":"ok"}`, upload → **202** `"status": "queued"`.

**Free ngrok:** add header `ngrok-skip-browser-warning: true` on the **Send to AI Backend** node (included in the repo workflow JSON). Without it, ngrok returns an HTML warning page instead of JSON.

### Notes

- Free ngrok URLs **change** when you restart the tunnel — update `FINANCE_API_URL` in n8n Cloud when that happens
- Keep `docker compose --profile tunnel up -d` running while n8n Cloud workflows are active
- Stop tunnel: `docker compose --profile tunnel stop ngrok`

### Production note

ngrok is **dev-only**. For production, deploy the API to a fixed HTTPS host (Azure, Fly.io, etc.) and point the n8n **Send to AI Backend** URL at that host. Self-hosted n8n on the same Docker network as the backend avoids a tunnel entirely (`outlook-invoice-ingest-docker.json`).

## Database migrations (email ingest)

Alembic chain for email ingest:

| Revision | Purpose |
|----------|---------|
| `m1n2o3p4q5r6` | `paid_amount` on matches (may already be applied on Supabase) |
| `p3q4r5s6t7u8` | `uploaded_files.upload_source` |
| `q4r5s6t7u8v9` | ingest metadata columns + backfill from `audit_logs` |

Apply on Supabase / local Postgres:

```powershell
docker compose exec backend alembic upgrade head
```

If Supabase was stamped at `m1n2o3p4q5r6` but columns were added manually, migrations are idempotent (they skip existing columns). To re-run the audit backfill only:

```powershell
docker compose exec backend python scripts/backfill_email_ingest.py
```

## n8n Cloud (general)

If your workflow lives on **n8n Cloud**, it runs on n8n’s servers — not your PC. It **cannot** call `localhost`, `backend:8000`, or `host.docker.internal`.

Use ngrok (above) or deploy the API to a fixed HTTPS host for production.

### n8n Cloud checklist

For your workflow on n8n Cloud:

1. **Credentials** — Microsoft Outlook OAuth2 + Header Auth `Borek Finance email ingest`
2. **Send to AI Backend** — full HTTPS URL to `/api/invoices/email-upload` (no `$vars` on free tier)
3. **Header Auth** provides `X-Email-Ingest-Key` (do not use session cookie)
4. **Body** — form field **`file`** (binary), plus metadata fields
5. **Remove Supabase insert nodes** if present — backend handles storage and DB
6. **Success** — HTTP **202** with `"status": "queued"` or `"duplicate"`

## Run n8n in Docker (self-hosted alternative)

n8n is defined in the root `docker-compose.yml` under the **`n8n` profile**, on the same network as the FastAPI backend.

### 1. Add to `.env`

```env
EMAIL_INGEST_API_KEY=your-long-random-secret
EMAIL_INGEST_USER_EMAIL=finance@borek.com
N8N_BASIC_AUTH_PASSWORD=choose-a-strong-password
OUTLOOK_FOLDER=Inbox
```

### 2. Start the stack

From the repo root:

```powershell
docker compose --profile n8n up -d
```

With frontend as well:

```powershell
docker compose --profile full --profile n8n up -d
```

Open **http://localhost:5678** (basic auth: `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD` from `.env`).

### 3. Import workflow and Outlook credential

1. **Workflows** → **Import from file** → `n8n/workflows/outlook-invoice-ingest.json`  
   (or pick from `/home/node/import-workflows` inside the container)
2. Create **Microsoft Outlook OAuth2** credential  
3. Azure app redirect URI: `http://localhost:5678/rest/oauth2-credential/callback`
4. Activate the workflow

Compose sets `FINANCE_API_URL=http://backend:8000` inside the n8n container — **do not use `localhost`** for the API URL.

### 4. Verify n8n → backend

From inside the n8n container:

```powershell
docker exec finance-ai-n8n wget -qO- http://backend:8000/api/health
```

Expected: `{"status":"ok"}`

## n8n environment variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `FINANCE_API_URL` | `http://backend:8000` (Compose) | API base (see networking below) |
| `EMAIL_INGEST_API_KEY` | same as backend `.env` | Header `X-Email-Ingest-Key` |
| `OUTLOOK_FOLDER` | `Inbox` or `Invoices` | Mailbox folder to watch |

### Networking

| n8n runs on | Use `FINANCE_API_URL` |
|-------------|------------------------|
| Docker Compose (this repo) | `http://backend:8000` |
| Docker, API on host only | `http://host.docker.internal:8000` |
| Same machine, not in Docker | `http://localhost:8000` |
| n8n Cloud | Public HTTPS URL to your API (not `localhost`) |
| n8n Cloud + local dev API | Tunnel URL, e.g. `https://xxxx.ngrok-free.app` |

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
- **URL:** `{{ $vars.FINANCE_API_URL }}/api/invoices/email-upload`  
- **Authentication:** None (use header below)  
- **Header:** `X-Email-Ingest-Key` = `{{ $vars.EMAIL_INGEST_API_KEY }}`  
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
