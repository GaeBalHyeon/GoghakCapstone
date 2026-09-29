@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tools\configure_telegram.py"
) else (
  python "tools\configure_telegram.py"
)

pause
