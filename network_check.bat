@echo off
setlocal
echo ============================================================
echo EV Fire Guard network check
echo ============================================================
echo.
echo Find the IPv4 Address of the Ethernet adapter connected to
echo the same router as the Jetson. Use that address for
echo WINDOWS_SERVER in jetson_agent/.env.
echo.
ipconfig
echo.
echo The Windows server must be running before testing port 8000.
echo Local health URL: http://127.0.0.1:8000/api/health
endlocal

