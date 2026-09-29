@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" tools\configure_windows.py
if errorlevel 1 exit /b 1
endlocal

