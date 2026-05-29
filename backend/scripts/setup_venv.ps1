# Create or refresh the local backend virtual environment (Windows).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File backend/scripts/setup_venv.ps1

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $BackendRoot ".venv\Scripts\python.exe"

Set-Location $BackendRoot

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at backend/.venv ..."
    python -m venv .venv
}

Write-Host "Upgrading pip ..."
& $VenvPython -m pip install --upgrade pip

Write-Host "Installing backend/requirements.txt ..."
& $VenvPython -m pip install -r requirements.txt

Write-Host ""
Write-Host "Done. Activate with:"
Write-Host "  cd backend"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Then run the API locally:"
Write-Host "  uvicorn main:app --reload --port 8000"
