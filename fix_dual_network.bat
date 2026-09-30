@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title EV Fire Guard - Dual Network Fix

echo ========================================
echo   EV Fire Guard - Dual Network Fix
echo ========================================
echo.
echo Wi-Fi will be used for Internet access.
echo Ethernet will remain connected to the Jetson LAN.
echo.

net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\fix_dual_network.ps1"
if errorlevel 1 goto :failed

echo.
type "data\network_fix_result.txt" 2>nul
echo.
echo Press any key to close.
pause >nul
endlocal
exit /b 0

:failed
echo [ERROR] Administrator network update failed.
type "data\network_fix_result.txt" 2>nul
pause
exit /b 1
