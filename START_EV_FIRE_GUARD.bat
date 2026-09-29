@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title EV Fire Guard

echo ========================================
echo   EV Fire Guard - One Click Start
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment is missing.
    echo Run setup.bat once, then try again.
    pause
    exit /b 1
)

sc query MySQL80 | find /I "RUNNING" >nul
if errorlevel 1 (
    echo [INFO] Starting MySQL...
    net start MySQL80 >nul 2>&1
    sc query MySQL80 | find /I "RUNNING" >nul
    if errorlevel 1 (
        echo [ERROR] MySQL could not be started.
        echo Right-click this BAT file and choose "Run as administrator".
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" "tools\prepare_launch.py"
set "PREPARE_RESULT=%ERRORLEVEL%"
if "%PREPARE_RESULT%"=="10" (
    echo [INFO] The server is already running. Opening the dashboard.
    start "" "http://127.0.0.1:8000"
    exit /b 0
)
if not "%PREPARE_RESULT%"=="0" (
    echo [ERROR] Startup check failed.
    pause
    exit /b %PREPARE_RESULT%
)

set /p DASHBOARD_URL=<"data\launch_url.txt"
if not defined DASHBOARD_URL set "DASHBOARD_URL=http://127.0.0.1:8000"

echo.
echo [READY] Windows server and Telegram configuration loaded.
echo [READY] Jetson connects using DESKTOP-TCULRT5.local:8000.
echo [OPEN]  %DASHBOARD_URL%
echo.
echo Keep this window open while the system is running.
echo Press Ctrl+C to stop the Windows server.
echo.

start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process '%DASHBOARD_URL%'"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log

echo.
echo EV Fire Guard server stopped.
pause
endlocal
