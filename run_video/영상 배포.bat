@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 화재 감지 카메라 실행기

set "PYTHON_EXE=..\.venv\Scripts\python.exe"
set "WINDOWS_SERVER=127.0.0.1:8000"

if not exist "%PYTHON_EXE%" (
  echo [오류] Python 가상환경이 없습니다.
  echo 먼저 setup_video_demo.bat를 실행하세요.
  pause
  exit /b 1
)

echo Windows 서버 주소: %WINDOWS_SERVER%
echo CAM-01은 카메라 0, CAM-02는 카메라 1을 사용합니다.
echo 카메라가 하나뿐이면 CAM-01 창만 사용하세요.
echo.

start "CAM-01 화재 감지" cmd /k ""%PYTHON_EXE%" "python\3f03.py""
start "CAM-02 화재 감지" cmd /k ""%PYTHON_EXE%" "python\3f07.py""

timeout /t 5 /nobreak >nul
"%PYTHON_EXE%" "python\url_parser.py"
echo.
echo 실행된 각 창에서 Ctrl+C를 누르면 해당 카메라가 종료됩니다.
pause
