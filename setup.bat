@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\Ria\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python 3 could not be found.
        echo Install Python 3.11 or later and run setup.bat again.
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Setup complete. Run run.bat to start EV Fire Guard.
endlocal

