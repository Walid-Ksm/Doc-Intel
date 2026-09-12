# ==============================================================================
# Document Intelligence Platform — Production Stack Teardown
# Stops and removes all production containers
# ==============================================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Stopping and removing production containers..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker compose -f docker-compose.prod.yml down

Write-Host "All production containers stopped successfully.`n" -ForegroundColor Green
