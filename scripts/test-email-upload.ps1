# Test POST /api/invoices/email-upload (Windows PowerShell 5.1+)
# Usage (from repo root):
#   $env:EMAIL_INGEST_API_KEY = "your-key"
#   .\scripts\test-email-upload.ps1 -FilePath "C:\path\to\invoice.pdf"

param(
    [string]$ApiUrl = "http://localhost:8000/api/invoices/email-upload",
    [string]$FilePath = "",
    [string]$ApiKey = $env:EMAIL_INGEST_API_KEY
)

if (-not $ApiKey) {
    Write-Error "Set EMAIL_INGEST_API_KEY in .env, then: `$env:EMAIL_INGEST_API_KEY = '...'"
    exit 1
}

if (-not $FilePath) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
    $defaultPng = Join-Path $repoRoot "backend\assets\branding\FinAI.png"
    if (Test-Path $defaultPng) {
        $FilePath = $defaultPng
    }
}

if (-not (Test-Path -LiteralPath $FilePath)) {
    Write-Error "File not found: $FilePath. Use -FilePath with a real PDF/PNG/JPG path."
    exit 1
}

$fileItem = Get-Item -LiteralPath $FilePath
$messageId = "ps-test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

Write-Host "POST $ApiUrl" -ForegroundColor Cyan
Write-Host "File: $($fileItem.FullName)" -ForegroundColor Gray

$curlArgs = @(
    "-s", "-S", "-w", "`nHTTP_STATUS:%{http_code}",
    "-X", "POST", $ApiUrl,
    "-H", "X-Email-Ingest-Key: $ApiKey",
    "-F", "file=@$($fileItem.FullName)",
    "-F", "source=outlook_email",
    "-F", "sender_email=vendor@example.com",
    "-F", "sender_name=Test Vendor",
    "-F", "email_subject=Test invoice from PowerShell",
    "-F", "message_id=$messageId",
    "-F", "attachment_name=$($fileItem.Name)"
)

$output = & curl.exe @curlArgs 2>&1
$text = ($output | Out-String).Trim()

if ($text -match "HTTP_STATUS:(\d+)$") {
    $status = [int]$Matches[1]
    $body = $text -replace "HTTP_STATUS:\d+\s*$", ""
} else {
    Write-Host $text
    Write-Error "curl failed (is curl.exe installed?)"
    exit 1
}

Write-Host "Status: $status" -ForegroundColor $(if ($status -eq 202) { "Green" } else { "Red" })
if ($body) { Write-Host $body }

if ($status -ne 202) { exit 1 }
