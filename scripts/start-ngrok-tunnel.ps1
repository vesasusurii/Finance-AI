# Start ngrok tunnel to expose the local Finance-AI API for n8n Cloud.
# Usage (from repo root):
#   1. Add NGROK_AUTHTOKEN to .env (https://dashboard.ngrok.com/get-started/your-authtoken)
#   2. .\scripts\start-ngrok-tunnel.ps1

param(
    [int]$InspectPort = 4040,
    [int]$WaitSeconds = 45
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repoRoot

function Get-DotEnvValue {
    param([string]$Name)
    $envFile = Join-Path $repoRoot ".env"
    if (-not (Test-Path $envFile)) { return $null }
    foreach ($line in Get-Content $envFile) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

$authtoken = $env:NGROK_AUTHTOKEN
if (-not $authtoken) {
    $authtoken = Get-DotEnvValue "NGROK_AUTHTOKEN"
}

if (-not $authtoken) {
    Write-Host ""
    Write-Host "NGROK_AUTHTOKEN is not set." -ForegroundColor Red
    Write-Host ""
    Write-Host "1. Sign up at https://ngrok.com (free tier is fine)"
    Write-Host "2. Copy your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken"
    Write-Host "3. Add to .env:"
    Write-Host "   NGROK_AUTHTOKEN=your_token_here"
    Write-Host "4. Run this script again"
    Write-Host ""
    exit 1
}

$env:NGROK_AUTHTOKEN = $authtoken

Write-Host "Starting backend (if needed) and ngrok tunnel..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker compose up -d backend 2>&1 | Out-Null
docker compose --profile tunnel up -d ngrok 2>&1 | Out-Null
$ErrorActionPreference = $prevEap

$inspectUrl = "http://127.0.0.1:$InspectPort/api/tunnels"
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$publicUrl = $null

Write-Host "Waiting for ngrok inspect API on port $InspectPort..." -ForegroundColor Gray

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Uri $inspectUrl -TimeoutSec 3
        $httpsTunnel = $response.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($httpsTunnel) {
            $publicUrl = $httpsTunnel.public_url.TrimEnd("/")
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $publicUrl) {
    Write-Host ""
    Write-Host "Could not read ngrok public URL." -ForegroundColor Red
    Write-Host "Recent ngrok logs:" -ForegroundColor Yellow
    docker logs finance-ai-ngrok 2>&1 | Select-Object -Last 15
    Write-Host ""
    Write-Host "If you see ERR_NGROK_105, check NGROK_AUTHTOKEN in .env and run:"
    Write-Host "  docker compose --profile tunnel up -d --force-recreate ngrok"
    exit 1
}

Write-Host ""
Write-Host "Tunnel is live" -ForegroundColor Green
Write-Host "  Public URL:   $publicUrl"
Write-Host "  Health:       $publicUrl/api/health"
Write-Host "  Email upload: $publicUrl/api/invoices/email-upload"
Write-Host "  Inspect UI:   http://127.0.0.1:$InspectPort"
Write-Host ""

Write-Host "Testing /api/health through tunnel..." -ForegroundColor Cyan
try {
    $healthHeaders = @{ "ngrok-skip-browser-warning" = "true" }
    $health = Invoke-RestMethod -Uri "$publicUrl/api/health" -Headers $healthHeaders -TimeoutSec 15
    $healthJson = $health | ConvertTo-Json -Compress
    Write-Host "  OK: $healthJson" -ForegroundColor Green
}
catch {
    $errMsg = $_.Exception.Message
    Write-Host "  Health check failed: $errMsg" -ForegroundColor Yellow
    Write-Host "  The tunnel may still be starting - retry in a few seconds."
}

Write-Host ""
Write-Host "n8n Cloud - set these Variables (Settings -> Variables):" -ForegroundColor Cyan
Write-Host "  FINANCE_API_URL       = $publicUrl"
Write-Host "  EMAIL_INGEST_API_KEY  = (same as EMAIL_INGEST_API_KEY in your .env)"
Write-Host "  OUTLOOK_FOLDER        = Inbox"
Write-Host ""
Write-Host 'Send to AI Backend node URL:'
Write-Host '  ={{ $vars.FINANCE_API_URL }}/api/invoices/email-upload'
Write-Host ""
Write-Host "Use `$vars` in expressions on n8n Cloud — `$env` is blocked (access to env vars denied)."
Write-Host ""
Write-Host "Note: free ngrok URLs change when you restart the tunnel. Re-run this script and update n8n if the URL changes."
Write-Host ""
