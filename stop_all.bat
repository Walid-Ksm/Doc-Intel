@echo off
REM =============================================================================
REM Document Intelligence Platform -- Local Stack Stopper
REM =============================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_all.ps1"
endlocal
