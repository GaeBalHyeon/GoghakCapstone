@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist "..\.venv\Scripts\python.exe" (
  py -3.11 -m venv "..\.venv"
)

"..\.venv\Scripts\python.exe" -m pip install --upgrade pip
"..\.venv\Scripts\python.exe" -m pip install torch==2.5.1+cpu torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu
"..\.venv\Scripts\python.exe" -m pip install numpy==1.26.4 ultralytics==8.3.0 websocket-client==1.8.0 python-dotenv

echo 설치가 완료되었습니다.
pause
