# Borek Finance — start the local Docker stack.
#
# Usage (from repo root):
#   .\start.ps1
#   .\start.ps1 -SkipBuild
#   .\start.ps1 -BackendOnly
#
# Double-click start.cmd if PowerShell blocks scripts.

param(
    [switch]$SkipBuild,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
Set-Location $repoRoot

function Test-DockerRunning {
    $null = docker info 2>&1
    return $LASTEXITCODE -eq 0
}

function Wait-ForApi {
    param([int]$TimeoutSeconds = 90)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 3
            if ($health.status -eq "ok") {
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

if (-not (Test-DockerRunning)) {
    Write-Host ""
    Write-Host "Docker is not running. Start Docker Desktop, wait until it is ready, then retry." -ForegroundColor Red
    Write-Host ""
    exit 1
}

$envFile = Join-Path $repoRoot ".env"
$envExample = Join-Path $repoRoot ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "Created .env from .env.example. Review secrets before production use." -ForegroundColor Yellow
        Write-Host ""
    }
    else {
        Write-Host ".env not found. Copy .env.example to .env and fill in required values." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Starting Borek Finance..." -ForegroundColor Cyan
Write-Host ""

$composeArgs = @("compose")
if ($BackendOnly) {
    $composeArgs += @("up", "-d", "db", "redis", "backend", "worker")
}
else {
    $composeArgs += @("--profile", "full", "up", "-d", "db", "redis", "backend", "worker", "frontend")
}

if (-not $SkipBuild) {
    $composeArgs += "--build"
}

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Waiting for API health..." -ForegroundColor Gray

if (Wait-ForApi) {
    Write-Host "Running database migrations..." -ForegroundColor Cyan
    docker compose exec -T backend alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Migrations failed. Check: docker compose logs backend" -ForegroundColor Yellow
    }
}
else {
    Write-Host "API did not become healthy in time." -ForegroundColor Yellow
    Write-Host "Check logs: docker compose logs backend" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Borek Finance is up" -ForegroundColor Green
Write-Host ""
if ($BackendOnly) {
    Write-Host "API:      http://localhost:8000/api/health"
    Write-Host "Frontend: run locally with  cd frontend; npm install; npm run dev"
}
else {
    Write-Host "Frontend: http://localhost:5173"
    Write-Host "API:      http://localhost:8000/api/health"
}
Write-Host ""
Write-Host "Stop stack:  docker compose --profile full down" -ForegroundColor DarkGray
Write-Host "Recover OCR: docker exec -w /app finance-ai-backend python scripts/recover_stuck_uploads.py" -ForegroundColor DarkGray
Write-Host ""
