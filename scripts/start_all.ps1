# =============================================================================
# Document Intelligence Platform -- Instant Multi-Service Launcher
# Launches all services in dedicated, titled terminal windows.
# =============================================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$ReportsRoot = if (Test-Path "$ProjectRoot\reports\mvnw.cmd") {
    Join-Path $ProjectRoot "reports"
} else {
    Resolve-Path (Join-Path $ProjectRoot "..\doc-intelligence-reports") -ErrorAction SilentlyContinue
}
$ShellExe = if (Get-Command pwsh.exe -ErrorAction SilentlyContinue) { "pwsh.exe" } else { "powershell.exe" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Document Intelligence Platform -- Instant Stack Launcher   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Start Docker Infrastructure
Write-Host ""
Write-Host "[1/5] Checking and starting Docker infrastructure..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker compose up -d

# 2. Sync APISIX Gateway Routes
Write-Host ""
Write-Host "[2/5] Configuring APISIX gateway routes..." -ForegroundColor Yellow
if (Test-Path "$ProjectRoot\venv\Scripts\python.exe") {
    & "$ProjectRoot\venv\Scripts\python.exe" "$ProjectRoot\infra\apisix\configure_apisix.py"
} else {
    python "$ProjectRoot\infra\apisix\configure_apisix.py"
}

# 3. Launch FastAPI P1 (:8000)
Write-Host ""
Write-Host "[3/5] Launching FastAPI P1 (:8000)..." -ForegroundColor Green
$cmd1 = "`$host.ui.RawUI.WindowTitle = 'DocIntelligence - FastAPI P1 (:8000)'; Set-Location '$ProjectRoot'; if (Test-Path 'venv\Scripts\Activate.ps1') { . .\venv\Scripts\Activate.ps1 }; python -m uvicorn app.main:app --reload --port 8000"
Start-Process $ShellExe -ArgumentList @("-NoExit", "-Command", $cmd1)

# 4. Launch Celery Worker
Write-Host ""
Write-Host "[4/5] Launching Celery Background Worker..." -ForegroundColor Green
$cmd2 = "`$host.ui.RawUI.WindowTitle = 'DocIntelligence - Celery Worker'; Set-Location '$ProjectRoot'; if (Test-Path 'venv\Scripts\Activate.ps1') { . .\venv\Scripts\Activate.ps1 }; python -m celery -A app.infrastructure.celery.celery_app worker --pool=threads --concurrency=2 --loglevel=info"
Start-Process $ShellExe -ArgumentList @("-NoExit", "-Command", $cmd2)

# 5. Launch Spring Boot Reports P2 (:8081)
if ($ReportsRoot -and (Test-Path "$ReportsRoot\mvnw.cmd")) {
    Write-Host ""
    Write-Host "[5/5] Launching Spring Boot Reports P2 (:8081)..." -ForegroundColor Green
    $cmd3 = "`$host.ui.RawUI.WindowTitle = 'DocIntelligence - Spring Boot Reports (:8081)'; Set-Location '$ReportsRoot'; .\mvnw.cmd spring-boot:run"
    Start-Process $ShellExe -ArgumentList @("-NoExit", "-Command", $cmd3)
}

# 6. Launch Angular Frontend (:4200)
if (Test-Path "$FrontendRoot\package.json") {
    Write-Host ""
    Write-Host "[+] Launching Angular Frontend (:4200)..." -ForegroundColor Green
    $cmd4 = "`$host.ui.RawUI.WindowTitle = 'DocIntelligence - Angular Frontend (:4200)'; Set-Location '$FrontendRoot'; npm start"
    Start-Process $ShellExe -ArgumentList @("-NoExit", "-Command", $cmd4)
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "All services launched successfully in dedicated windows!" -ForegroundColor Cyan
Write-Host "  - APISIX Ingress Gateway: http://localhost:9080" -ForegroundColor White
Write-Host "  - Angular Frontend:       http://localhost:4200" -ForegroundColor White
Write-Host "  - Keycloak IAM:           http://localhost:8080" -ForegroundColor White
Write-Host "  - FastAPI P1 (Direct):    http://localhost:8000" -ForegroundColor Gray
Write-Host "  - Spring Boot P2 (Direct):http://localhost:8081" -ForegroundColor Gray
Write-Host "  - MinIO Storage Console:  http://localhost:9001" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "To stop the running services, run: .\scripts\stop_all.ps1`n" -ForegroundColor DarkGray
