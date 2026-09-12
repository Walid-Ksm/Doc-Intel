# ==============================================================================
# Document Intelligence Platform — Production Stack Launcher
# Builds and starts all production containers with unified healthchecks
# ==============================================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Document Intelligence Platform — Production Launcher    " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Set-Location $ProjectRoot

# 1. Ensure production env file exists
if (-not (Test-Path "$ProjectRoot\.env.prod")) {
    if (Test-Path "$ProjectRoot\.env.prod.example") {
        Write-Host "Creating .env.prod from template..." -ForegroundColor Yellow
        Copy-Item "$ProjectRoot\.env.prod.example" "$ProjectRoot\.env.prod"
    }
}

# 2. Build and launch all production containers
Write-Host ""
Write-Host "Building and launching containers via docker-compose.prod.yml..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Container build or startup failed. Please inspect the error above." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 3. Summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Production Stack is active!" -ForegroundColor Cyan
Write-Host "  - Angular Web Application: http://localhost:4200" -ForegroundColor White
Write-Host "  - APISIX Ingress Gateway:  http://localhost:9080" -ForegroundColor White
Write-Host "  - Keycloak IAM:            http://localhost:8080" -ForegroundColor White
Write-Host "  - FastAPI Core Service:    http://localhost:8000" -ForegroundColor Gray
Write-Host "  - Spring Boot Reports:     http://localhost:8081" -ForegroundColor Gray
Write-Host "  - MinIO Storage Console:   http://localhost:9001" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "To view logs: docker compose -f docker-compose.prod.yml logs -f" -ForegroundColor DarkGray
Write-Host "To stop:      .\scripts\prod_down.ps1`n" -ForegroundColor DarkGray
