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

# Get ngrok token
$authtoken = $env:NGROK_AUTHTOKEN
if (-not $authtoken) {
    $authtoken = Get-DotEnvValue "NGROK_AUTHTOKEN"
}

if (-not $authtoken) {
    Write-Host ""
    Write-Host "NGROK_AUTHTOKEN is not set." -ForegroundColor Red
    Write-Host ""
    Write-Host "1. Sign up at https://ngrok.com"
    Write-Host "2. Get token from https://dashboard.ngrok.com/get-started/your-authtoken"
    Write-Host "3. Add to .env:"
    Write-Host "   NGROK_AUTHTOKEN=your_token_here"
    Write-Host ""
    exit 1
}

$env:NGROK_AUTHTOKEN = $authtoken

Write-Host "Starting backend + ngrok tunnel..." -ForegroundColor Cyan

# Start services
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"

docker compose up -d backend 2>&1 | Out-Null
docker compose --profile tunnel up -d ngrok 2>&1 | Out-Null

$ErrorActionPreference = $prevEap

$inspectUrl = "http://127.0.0.1:$InspectPort/api/tunnels"
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$publicUrl = $null

Write-Host "Waiting for ngrok..." -ForegroundColor Gray

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
    Write-Host "Could not read ngrok URL." -ForegroundColor Red
    Write-Host "Recent logs:" -ForegroundColor Yellow
    docker logs finance-ai-ngrok 2>&1 | Select-Object -Last 15
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Tunnel is live" -ForegroundColor Green
Write-Host "Public URL: $publicUrl"
Write-Host "Health: $publicUrl/api/health"
Write-Host "Email upload: $publicUrl/api/invoices/email-upload"
Write-Host ""

# Test health endpoint
Write-Host "Testing health..." -ForegroundColor Cyan

try {
    $headers = @{ "ngrok-skip-browser-warning" = "true" }
    $health = Invoke-RestMethod -Uri "$publicUrl/api/health" -Headers $headers -TimeoutSec 15
    Write-Host ("OK: " + ($health | ConvertTo-Json -Compress)) -ForegroundColor Green
}
catch {
    Write-Host "Health check failed (tunnel may still be warming up)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "n8n Cloud configuration:" -ForegroundColor Cyan
Write-Host "FINANCE_API_URL = $publicUrl"
Write-Host "EMAIL_INGEST_API_KEY = same as .env"
Write-Host "OUTLOOK_FOLDER = Inbox"
Write-Host ""

Write-Host "Use this in n8n HTTP node:"
Write-Host "$publicUrl/api/invoices/email-upload"
Write-Host ""

Write-Host "Note: ngrok free URLs change on restart. Re-run script when needed." -ForegroundColor DarkGray
Write-Host ""