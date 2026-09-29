# 현재 작업 인수인계

작성일: 2026-09-29  
저장소: `https://github.com/GaeBalHyeon/GoghakCapstone`

## 1. 최종 목표

- Windows PC가 FastAPI 홈페이지와 로컬 MySQL을 실행한다.
- Jetson에 연결된 카메라 영상을 Jetson의 `best.pt` YOLO 모델로 화재·연기 추론한다.
- Jetson은 바운딩 박스가 그려진 실시간 JPEG 프레임과 확정 이벤트를 Windows 서버로 WebSocket 전송한다.
- 홈페이지의 기존 주차장 배치도 `CAM-01` 위치에 Jetson 실시간 YOLO 영상을 표시한다.
- 배치도 `CAM-02~04` 위치에는 Windows `video/1.mp4~3.mp4`를 실시간 관제 영상처럼 자동·무음·무한 반복한다.
- 감지 이벤트는 Windows 로컬 MySQL에 저장한다.

## 2. 현재 구현 상태

### Windows 서버

- FastAPI 서버 실행: `run.bat` 또는 호환 실행기 `start_server.bat`
- 외부 장비 접속 주소: `0.0.0.0:8000`
- Jetson WebSocket: `/ws/edge/{camera_id}?token=EDGE_TOKEN`
- Jetson MJPEG 중계: `/api/video_feed/{camera_id}`
- Windows MP4 제공: `/videos/*.mp4`
- 이벤트 조회, 확인, 전체 삭제 API 구현
- 자동 시뮬레이션 기본값 OFF

### 홈페이지

- 별도 카메라 카드나 저장 영상 페이지는 사용하지 않는다.
- 기존 주차장 배치도의 네 카메라 위치 자체가 영상 패널이다.
- `CAM-01`: Jetson 연결 전 `OFFLINE`, 연결 후 `JETSON LIVE`
- `CAM-02`: `video/1.mp4`
- `CAM-03`: `video/2.mp4`
- `CAM-04`: `video/3.mp4`
- 로컬 영상은 `LOCAL LIVE`로 표시되고 자동·무음·반복 재생된다.
- 영상 패널을 누르면 감지 테스트 대상 카메라가 선택된다.

### Jetson 에이전트

- 코드 위치: `jetson_agent/agent.py`
- 모델 위치: `jetson_agent/best.pt`
- 모델 클래스: `{0: fire, 1: smoke}`
- SHA-256: `331E95833A3E7E865C8F7F846585561084F1159FB9443834A786AF2C22CB6FC8`
- 최근 20프레임 중 10회 이상 감지 시 이벤트를 확정한다.
- 서버 연결이 끊긴 동안 확정 이벤트를 대기 큐에 보관한다.
- `jetson_agent/diagnose.py`가 CUDA, 카메라, 모델, HTTP, Edge WebSocket 토큰 인증을 검사한다.

## 3. 완료된 검증

- Windows CPU에서 `best.pt` 실제 로드 및 화재·연기 클래스 확인
- 테스트 영상으로 YOLO → WebSocket → Windows MJPEG → 이벤트 DB 저장 종단 간 검증
- Jetson 연결/종료 시 홈페이지 온라인/오프라인 상태 전환 검증
- 세 Windows MP4 모두 HTTP Range 요청 `206 Partial Content` 확인
- 브라우저에서 세 로컬 영상 `readyState=4`, `paused=false`, 원본 해상도 인식 확인
- 브라우저에서 주차장 배치도 상단과 하단에 네 영상 패널이 겹치지 않고 표시되는 것을 확인
- `tests/edge_integration.py`에서 토큰 인증, CAM 매핑, MP4 Range, JPEG, FPS, 이벤트 저장과 정리를 통합 검사

통합 검사 실행 예시:

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone
.venv\Scripts\python.exe tests\edge_integration.py 8000
```

## 4. 아직 완료되지 않은 실제 장비 작업

### MySQL (2026-09-29 완료)

- `configure_windows.bat`으로 DB `ev_fire_guard`, 계정 `evguard`, 테이블, `.env`, `EDGE_TOKEN`을 생성했다.
- MySQL 8 기본 인증(`caching_sha2_password`)에 필요한 `cryptography==44.0.0`을 `requirements.txt`에 추가했다.
- 관리자 CMD에서 `allow_firewall_8000.bat`으로 개인 네트워크 TCP 8000 인바운드 규칙을 추가했다.
- `run.bat` 실행 시 `/api/health`가 `database: mysql`을 반환한다.
- `diagnose_windows.bat` 9/9 PASS, `tests\edge_integration.py`와 `tests\mysql_integration.py` 모두 통과했다.
- Windows 측 남은 작업은 없으며, Jetson `.env`의 `EDGE_TOKEN`에 Windows `.env`의 값을 복사하면 된다.

### Jetson 실장 (2026-09-29 연결 완료)

- 장비: Jetson Orin Nano Super, JetPack 6 (L4T R36.4.7, CUDA 12.6, cuDNN 9.3), 계정 `pangsu`
- 현재 공유기: Windows `192.168.0.223`, Jetson `192.168.0.117` (Jetson은 `192.168.0.201`로도 접속됨)
- Windows 네트워크 프로필을 "개인"으로 변경해야 8000 방화벽 규칙이 적용된다.
- Windows → Jetson SSH 키: `C:\Users\Ria\.ssh\evguard_jetson` (Jetson `authorized_keys`의 `ria-pc-evguard`)
- 설치 위치: `~/evguard/jetson_agent`, 전용 가상환경 `~/evguard/venv`
- 기존 시스템/사용자 PyTorch가 cuDNN 8·CPU 빌드로 꼬여 있어 건드리지 않고, venv에 jetson-ai-lab `jp6/cu126` 인덱스의 `torch==2.8.0`, `torchvision==0.23.0`을 설치했다. (`--index-url`로 이 인덱스만 지정해야 CPU 빌드로 바뀌지 않는다.)
- venv 추가 패키지: `ultralytics==8.3.0`, `numpy==1.26.4`, `opencv-python-headless==4.10.0.84`, `websocket-client==1.8.0`, `python-dotenv==1.0.1`
- 실행: `~/evguard/run_agent.sh` (로그 `~/evguard/agent.log`), 중지: `~/evguard/stop_agent.sh`
- `diagnose.py` 8/8 PASS, USB 카메라 `/dev/video0` 640x480, GPU 추론 약 27 FPS, 서버 MJPEG 약 7 FPS 수신 확인
- `agent.py`가 서버의 WebSocket ping에 응답하지 않아 약 40초마다 끊기던 문제를 수신 스레드 추가로 수정했다.
- 아직 확인하지 않은 것: 실제 화재·연기 장면에서 이벤트가 MySQL에 `source=jetson-yolo`로 저장되는지, Jetson 재부팅 시 자동 실행

아래는 처음부터 새 Jetson에 설치할 때의 참고 절차다.

```bash
git clone https://github.com/GaeBalHyeon/GoghakCapstone.git
cd GoghakCapstone/jetson_agent
cp .env.example .env
chmod +x setup_jetson.sh
./setup_jetson.sh
python3 diagnose.py
python3 agent.py
```

Jetson `.env` 핵심값:

```dotenv
WINDOWS_SERVER=WINDOWS_LAN_IP:8000
EDGE_TOKEN=Windows_.env와_동일한_값
CAMERA_ID=CAM-01
CAMERA_SOURCE=0
MODEL_PATH=best.pt
CONFIDENCE=0.45
TARGET_FPS=8
WINDOW_SIZE=20
MIN_DETECTIONS=10
```

## 5. 실제 연결 순서

1. Windows와 Jetson을 같은 공유기에 유선 연결한다.
2. Windows에서 `network_check.bat`으로 LAN IP를 확인한다.
3. 관리자 CMD에서 `allow_firewall_8000.bat`을 한 번 실행한다.
4. `configure_windows.bat`으로 MySQL과 `.env`를 구성한다.
5. Windows에서 `run.bat`을 실행한다.
6. Jetson `.env`에 Windows IP와 동일한 `EDGE_TOKEN`을 입력한다.
7. Jetson에서 `python3 diagnose.py`의 모든 항목이 PASS인지 확인한다.
8. Jetson에서 `python3 agent.py`를 실행한다.
9. 홈페이지 배치도 `CAM-01`에 `JETSON LIVE` 영상이 표시되는지 확인한다.
10. 화재·연기 이벤트가 MySQL `events` 테이블에 `source=jetson-yolo`로 저장되는지 확인한다.

## 6. 주의사항

- `.env`, DB 비밀번호, Edge 토큰은 GitHub에 올리지 않는다.
- Jetson의 CUDA용 PyTorch를 일반 CPU PyTorch로 덮어쓰지 않는다.
- `run_video/python/best.pt`는 화재·연기 모델이다.
- 두 `yolo11s.pt`는 서로 동일한 COCO 80클래스 기본 모델이며 화재 학습 모델이 아니다.
- `run_video/python/cloudflared.exe`는 현재 구조에서 사용하지 않으며 Git에서 제외되어 있다.
- 자동 시뮬레이션은 사용자가 직접 켤 때만 동작해야 한다.

## 7. 관련 문서

- `handoff/AI_HANDOFF_2026-09-29.md`: 2026-09-29 세션 결과, 남은 작업, AI 작업 요령
- `JETSON_HANDOFF.md`: Jetson 상세 설정과 네트워크 규격
- `WORK_LOG.md`: 전체 작업 이력
- `MODEL_EVALUATION.md`: 모델 및 영상 평가 결과
- `run_video/README.md`: 기존 영상 배포 폴더 전환 내용

현재 작업은 사용자의 요청에 따라 여기서 일시정지한다. 다음 작업자는 먼저 `git status`와 이 문서를 확인한 뒤 실제 MySQL 구성 또는 Jetson 장비 검증부터 이어서 진행한다.
