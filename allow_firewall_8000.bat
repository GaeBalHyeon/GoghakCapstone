@echo off
setlocal
net session >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Run this file from an Administrator CMD.
    exit /b 1
)

echo Adding a Windows Firewall rule for TCP 8000 on Private networks...
netsh advfirewall firewall delete rule name="EV Fire Guard Server" >nul 2>nul
netsh advfirewall firewall add rule name="EV Fire Guard Server" dir=in action=allow protocol=TCP localport=8000 profile=private
if errorlevel 1 exit /b 1
echo Firewall rule added.
endlocal

