# =============================================================================
# Document Intelligence Platform — One-Click Development Stopper
# Gracefully terminates host services (FastAPI, Celery, Spring Boot, Angular)
# =============================================================================

Write-Host "Stopping DocIntelligence host services..." -ForegroundColor Yellow

# Ports to free: 8000 (FastAPI), 8081 (Spring Boot), 4200 (Angular)
$Ports = @(8000, 8081, 4200)

foreach ($Port in $Ports) {
    $Conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($Conns) {
        foreach ($Conn in $Conns) {
            $PidToKill = $Conn.OwningProcess
            try {
                $Proc = Get-Process -Id $PidToKill -ErrorAction SilentlyContinue
                if ($Proc) {
                    Write-Host "Stopping process $($Proc.ProcessName) (PID: $PidToKill) listening on port $Port..." -ForegroundColor Gray
                    Stop-Process -Id $PidToKill -Force -ErrorAction SilentlyContinue
                }
            } catch {}
        }
    }
}

# Stop Celery processes (on Windows, Celery runs under python.exe)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { 
    $_.CommandLine -and $_.CommandLine -like "*celery*" -and ($_.Name -like "*python*" -or $_.Name -like "*celery*")
} | ForEach-Object {
    Write-Host "Stopping Celery process $($_.Name) (PID: $($_.ProcessId))..." -ForegroundColor Gray
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

# Stop spawned DocIntelligence PowerShell/Terminal windows
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -like "*DocIntelligence - *" -and ($_.Name -like "*pwsh*" -or $_.Name -like "*powershell*")
} | ForEach-Object {
    Write-Host "Closing terminal window (PID: $($_.ProcessId))..." -ForegroundColor Gray
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "Host services stopped." -ForegroundColor Green
Write-Host "Note: Docker containers remain running. To stop containers too, run: docker compose down" -ForegroundColor Cyan
