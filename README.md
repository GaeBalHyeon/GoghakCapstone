# EV Fire Guard Local

전기차 주차장의 CCTV 영상을 바탕으로 화재·연기를 조기에 감지하고, 주차장 도면과 이벤트 로그를 통해 관리자의 초기 대응을 돕는 로컬 관제 프로젝트입니다.

현재 PC에는 Jetson, CCTV, mmWave 센서가 연결되어 있지 않으므로 기본 모드는 **장비 없는 시뮬레이션 모드**입니다. 관제 화면에서 카메라별 화재·연기 이벤트를 직접 발생시킬 수 있고, 자동 시뮬레이터도 제공합니다.

## 실행 방법

명령 프롬프트(CMD)에서 다음 명령을 실행합니다.

```bat
cd C:\Users\Ria\Desktop\capstone\re_capstone
setup.bat
run.bat
```

최초 한 번만 `setup.bat`을 실행하면 됩니다. 이후에는 `run.bat`만 실행하면 됩니다. 서버를 종료할 때는 CMD 창에서 `Ctrl+C`를 누릅니다.

설치 스크립트는 이 PC의 Codex 내장 Python을 먼저 사용하며, 없으면 시스템 Python을 찾습니다. PowerShell용 `setup.ps1`, `run.ps1`도 보조 실행 파일로 유지했습니다.

GitHub에 현재 변경 내용을 업로드할 때는 `push.bat`을 실행합니다. 이 PC의 Git이 CMD PATH에 없어도 프로젝트에 연결된 Git 실행 파일을 자동으로 사용합니다.

브라우저에서 <http://127.0.0.1:8000>에 접속합니다. API 문서는 <http://127.0.0.1:8000/docs>에서 확인할 수 있습니다.

서버는 `0.0.0.0:8000`에 바인딩되므로 같은 공유기의 Jetson에서도 접속할 수 있습니다. `network_check.bat`으로 Windows 내부 IP를 확인하고, 관리자 CMD에서 `allow_firewall_8000.bat`을 한 번 실행해 개인 네트워크 TCP 8000을 허용합니다.

이 PC에는 MySQL 8.0 서비스가 설치되어 실행 중입니다. `setup.bat` 실행 후 `configure_windows.bat`을 실행하면 MySQL 관리자 비밀번호를 숨김 입력으로 받아 DB, 애플리케이션 계정, 테이블, `.env`와 Edge 토큰을 자동 생성합니다. 기존 `.env`는 `.env.backup`으로 보관됩니다.

```bat
setup.bat
configure_windows.bat
.venv\Scripts\python.exe tests\mysql_integration.py
diagnose_windows.bat
run.bat
```

`diagnose_windows.bat`은 `.env`, MySQL 서비스와 로그인, 서버 포트, YOLO 모델, 테스트 영상, LAN 주소를 한 번에 점검합니다.

## 구현 기능

- 지하 1층 도면에 4개 카메라 위치와 상태 표시
- 화재·연기·정상 수동 시나리오 실행
- 자동 이벤트 시뮬레이터 및 발생 간격 설정
- WebSocket을 통한 실시간 화면 갱신
- 화재·연기 경보 배너와 브라우저 경보음
- 이벤트 시각, 구역, 충전기, 신뢰도, 해제 상태 기록
- 감지 순간 스냅샷 저장·확대와 Telegram 휴대폰 경보
- 3초 연속 감지 후 화재·연기 확정(순간 오탐 억제)
- MySQL 운영 DB와 SQLite 개발 DB
- 관리자 확인 및 이벤트 해제

Telegram은 `configure_telegram.bat`을 실행해 봇 토큰과 휴대폰 채팅을 연결합니다. 비밀값은 GitHub에 올라가지 않는 `.env`에만 저장됩니다.
일시적인 인터넷 오류나 Telegram 서버 오류가 발생하면 기본 2초, 5초 간격으로 최대 3회 전송을 시도합니다. 잘못된 토큰처럼 재시도로 해결되지 않는 오류는 즉시 실패 처리합니다.

## 실제 장비 연결 시 교체할 부분

`app/main.py`의 `register_detection()` API가 장비와 웹 관제 사이의 접점입니다. Jetson 또는 별도 추론 프로그램이 아래 형식으로 결과를 보내면 현재 화면과 DB를 그대로 사용할 수 있습니다.

```json
{
  "camera_id": "CAM-01",
  "event_type": "fire",
  "confidence": 0.94,
  "source": "jetson-yolo"
}
```

Jetson 연결 구조와 실제 장비 작업 절차는 `JETSON_HANDOFF.md`를 확인합니다. Jetson은 YOLO 추론 영상과 이벤트를 WebSocket으로 Windows에 전송하고, Windows는 홈페이지 영상 중계와 MySQL 저장을 담당합니다. mmWave 센서는 화재 탐지의 주 센서가 아니라 재실자 확인이나 대피 보조 데이터로 결합할 수 있습니다.

모델의 Windows CPU 영상 평가와 종단 간 전송 검증 결과는 `MODEL_EVALUATION.md`에 기록되어 있습니다.

## 폴더 구성

```text
re_capstone/
├─ app/main.py          FastAPI, SQLite, WebSocket, 시뮬레이터
├─ app/database.py      SQLite/MySQL 연결 계층
├─ jetson_agent/        Jetson 카메라·YOLO 전송 프로그램
├─ static/              관제 대시보드
├─ data/                실행 시 SQLite DB 생성
├─ requirements.txt
├─ setup.bat
├─ setup_mysql.bat
├─ run.bat
├─ network_check.bat
├─ allow_firewall_8000.bat
├─ setup.ps1
├─ run.ps1
├─ JETSON_HANDOFF.md
└─ WORK_LOG.md
```

