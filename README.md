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

## 구현 기능

- 지하 1층 도면에 4개 카메라 위치와 상태 표시
- 화재·연기·정상 수동 시나리오 실행
- 자동 이벤트 시뮬레이터 및 발생 간격 설정
- WebSocket을 통한 실시간 화면 갱신
- 화재·연기 경보 배너와 브라우저 경보음
- 이벤트 시각, 구역, 충전기, 신뢰도, 해제 상태 기록
- SQLite 로컬 데이터베이스
- 관리자 확인 및 이벤트 해제

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

YOLO 추론, RTSP 수집, 스냅샷 저장은 실제 카메라와 학습 모델을 확보한 뒤 별도 워커로 추가하는 구성을 권장합니다. mmWave 센서는 화재 탐지의 주 센서가 아니라 재실자 확인이나 대피 보조 데이터로 결합할 수 있습니다.

## 폴더 구성

```text
re_capstone/
├─ app/main.py          FastAPI, SQLite, WebSocket, 시뮬레이터
├─ static/              관제 대시보드
├─ data/                실행 시 SQLite DB 생성
├─ requirements.txt
├─ setup.bat
├─ run.bat
├─ setup.ps1
├─ run.ps1
└─ WORK_LOG.md
```

