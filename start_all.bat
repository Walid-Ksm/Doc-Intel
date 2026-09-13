@echo off
REM =============================================================================
REM Document Intelligence Platform -- Local Stack Launcher
REM =============================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_all.ps1"
endlocal
