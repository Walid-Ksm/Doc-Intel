# Run Celery Worker for Document Intelligence Service
# Note: On Windows, Celery requires --pool=threads or --pool=solo (the default prefork pool is not supported on Windows)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

# Activate virtual environment if present
if (Test-Path "$ProjectRoot\venv\Scripts\Activate.ps1") {
    & "$ProjectRoot\venv\Scripts\Activate.ps1"
}

Write-Host "Starting Celery worker for doc_intelligence..." -ForegroundColor Cyan
Write-Host "Concurrency: 2 threads (Windows pool: threads)" -ForegroundColor Gray

celery -A app.infrastructure.celery.celery_app worker --pool=threads --concurrency=2 --loglevel=info
