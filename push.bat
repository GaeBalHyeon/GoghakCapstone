@echo off
setlocal
cd /d "%~dp0"

set "GIT_EXE=C:\Users\Ria\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"

if not exist "%GIT_EXE%" (
    where git >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Git could not be found.
        echo Install Git for Windows or add git.exe to PATH.
        exit /b 1
    )
    set "GIT_EXE=git"
)

echo Uploading the main branch to GitHub...
"%GIT_EXE%" push -u origin main
if errorlevel 1 (
    echo.
    echo [ERROR] Upload failed. Complete GitHub authentication and try again.
    exit /b 1
)

echo.
echo Upload complete.
endlocal

