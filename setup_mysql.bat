@echo off
setlocal
cd /d "%~dp0"
set "MYSQL_EXE=C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"

if not exist "%MYSQL_EXE%" (
    where mysql >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] MySQL client was not found.
        exit /b 1
    )
    set "MYSQL_EXE=mysql"
)

echo Before continuing, edit mysql_setup.sql and .env so the
echo evguard passwords are identical.
echo Enter the MySQL root password when prompted.
echo.
"%MYSQL_EXE%" -u root -p < mysql_setup.sql
if errorlevel 1 exit /b 1
echo MySQL database and application user are ready.
endlocal

