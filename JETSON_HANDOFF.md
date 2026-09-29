# Jetson 작업 인수인계

이 문서는 Jetson에서 작업하는 Codex와 개발자가 Windows 측 구현 상태를 확인하고 후속 작업을 이어가기 위한 기준 문서입니다. 모든 장비 관련 변경과 검증 결과는 이 문서와 `WORK_LOG.md`에 기록합니다.

## 목표 구조

```text
Jetson 카메라 → OpenCV → YOLO 화재·연기 추론
                       ↓ WebSocket (JPEG + 이벤트)
                  공유기 / 동일 LAN
                       ↓
Windows FastAPI → 실시간 홈페이지 + 로컬 MySQL
```

Jetson은 카메라와 AI 추론을 담당합니다. Windows PC는 영상 중계, 홈페이지, 이벤트 기록과 MySQL을 담당합니다. 브라우저는 Windows 서버에만 접속합니다.

## GitHub와 공유기의 역할

- GitHub는 Windows와 Jetson이 동일한 소스와 문서를 공유하는 기준 저장소입니다.
- 공유기는 실행 중인 영상과 이벤트를 전송하는 네트워크입니다. 파일을 자동으로 동기화하지 않습니다.
- `.env`, DB 비밀번호, 토큰, RTSP 인증 정보는 GitHub에 올리지 않습니다.
- 인터넷이 없는 시연 환경에서는 미리 저장소를 clone하거나 Windows에서 `scp`로 전달합니다.

Jetson 최초 준비:

```bash
git clone https://github.com/GaeBalHyeon/GoghakCapstone.git
cd GoghakCapstone/jetson_agent
cp .env.example .env
```

Windows에서 코드가 변경된 뒤 Jetson에서 갱신:

```bash
cd ~/GoghakCapstone
git pull origin main
```

## 공유기 구성 권장안

두 장비를 같은 공유기에 유선 LAN으로 연결하는 방식을 권장합니다. 인터넷 연결은 최초 설치 이후 필수가 아닙니다.

| 장비 | 예시 IP | 역할 |
|---|---:|---|
| 공유기 | `192.168.50.1` | 내부 네트워크와 DHCP |
| Windows | `192.168.50.10` | FastAPI, MySQL, 홈페이지 |
| Jetson | `192.168.50.20` | 카메라, YOLO |

공유기에서 각 장비의 MAC 주소를 기준으로 DHCP 예약을 설정하면 IP가 바뀌지 않습니다. 시연 안정성을 위해 Wi-Fi보다 기가비트 유선 LAN을 권장합니다.

연결 확인:

```text
Windows CMD: ping 192.168.50.20
Jetson:      ping 192.168.50.10
Jetson:      curl http://192.168.50.10:8000/api/health
```

Windows 방화벽에서는 개인 네트워크의 TCP 8000 포트만 허용합니다. 외부 인터넷에 8000 포트를 개방할 필요는 없습니다.

현재 확인 당시 Windows PC의 유선 LAN 주소는 `192.168.1.138`, 게이트웨이는 `192.168.1.1`이었습니다. DHCP 주소는 바뀔 수 있으므로 실제 연결 직전에 `network_check.bat`으로 다시 확인하고 공유기에서 DHCP 예약을 설정합니다.

## Windows 설정

`setup.bat` 실행 후 `configure_windows.bat`을 실행합니다. MySQL 관리자 비밀번호는 화면에 표시되지 않으며, 도구가 DB, 애플리케이션 계정, 테이블, `.env`와 랜덤 Edge 토큰을 생성합니다.

```bat
setup.bat
configure_windows.bat
.venv\Scripts\python.exe tests\mysql_integration.py
allow_firewall_8000.bat
run.bat
```

생성된 Windows `.env`의 `EDGE_TOKEN` 값을 Jetson `jetson_agent/.env`에 복사합니다. `.env`와 `.env.backup`은 Git에 포함되지 않습니다.

`allow_firewall_8000.bat`은 관리자 권한 CMD에서 한 번만 실행합니다. `run.bat`은 외부 장비 접속이 가능하도록 `0.0.0.0:8000`에서 서버를 엽니다.

MySQL 관리자 계정으로 `mysql_setup.sql`을 한 번 실행합니다. SQL 파일과 `.env`의 비밀번호는 동일하게 변경합니다.

## Jetson 설정

Jetson용 코드는 `jetson_agent` 폴더에 있습니다.

```bash
cd jetson_agent
chmod +x setup_jetson.sh
./setup_jetson.sh
python3 diagnose.py
python3 agent.py
```

`.env` 예시:

```dotenv
WINDOWS_SERVER=192.168.50.10:8000
EDGE_TOKEN=Windows와 동일한 토큰
CAMERA_ID=CAM-01
CAMERA_SOURCE=0
MODEL_PATH=best.pt
CONFIDENCE=0.45
TARGET_FPS=8
CONFIRM_SECONDS=3.0
MISS_TOLERANCE_SECONDS=0.6
CLEAR_SECONDS=2.0
```

USB 카메라는 `CAMERA_SOURCE=0`, RTSP 카메라는 `CAMERA_SOURCE=rtsp://...`를 사용합니다.

## 모델 확인

원본 프로젝트의 `best.pt`를 `jetson_agent/best.pt`로 포함했습니다. 모델을 실행하지 않고 PyTorch 아카이브 메타데이터를 검사한 결과 클래스는 `{0: fire, 1: smoke}`입니다.

```text
파일 크기: 19,167,642 bytes
SHA-256: 331E95833A3E7E865C8F7F846585561084F1159FB9443834A786AF2C22CB6FC8
```

모델 클래스에 `fire` 또는 `smoke`가 있어야 현재 에이전트가 이벤트로 분류합니다. Jetson에서 로드한 뒤에도 아래 명령으로 확인합니다.

```bash
python3 -c "from ultralytics import YOLO; print(YOLO('best.pt').names)"
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA unavailable')"
```

클래스 이름이 다르면 `agent.py`의 `class_kind()`를 실제 모델에 맞게 수정합니다. JetPack의 CUDA용 PyTorch를 일반 CPU 패키지로 덮어쓰지 않도록 주의합니다. `diagnose.py`의 출력 전문을 `WORK_LOG.md`에 기록하고 모든 항목이 PASS인지 확인합니다.

## 통신 규격

Jetson 연결 주소:

```text
ws://WINDOWS_IP:8000/ws/edge/CAM-01?token=EDGE_TOKEN
```

- Binary 메시지: YOLO 박스가 그려진 JPEG 프레임
- Text 메시지: FPS heartbeat 또는 확정 화재·연기 이벤트
- 홈페이지 영상: `http://WINDOWS_IP:8000/api/video_feed/CAM-01`
- 감지 이벤트: Windows MySQL의 `events` 테이블에 `source=jetson-yolo`로 저장

화재와 연기는 기본적으로 3초간 지속 검출됐을 때 확정됩니다. 0.6초 이하의 순간 누락은 허용하며 2초간 검출이 없으면 정상 복귀합니다.

## 실제 장비 검증 순서

1. Windows와 Jetson 양방향 ping 확인
2. Jetson에서 Windows `/api/health` 확인
3. Jetson OpenCV 카메라 입력 확인
4. `best.pt` 클래스 및 CUDA 확인
5. Windows `run.bat` 실행
6. `python3 diagnose.py`에서 카메라, CUDA, 모델, HTTP, 토큰 인증 WebSocket이 모두 PASS인지 확인
7. Jetson `agent.py` 실행
8. 홈페이지 카메라 카드가 `JETSON LIVE`로 바뀌는지 확인
9. 화재·연기 영상으로 이벤트 생성 확인
10. MySQL 저장 확인
11. Jetson 종료 시 홈페이지 오프라인 전환 확인

## 아직 장비에서 확인할 내용

- Jetson 모델과 JetPack 버전
- 카메라 종류와 장치 번호
- `best.pt` 실제 클래스
- CUDA/TensorRT 추론 속도
- 실제 Windows와 Jetson 내부 IP
- 실제 영상에 맞는 신뢰도와 프레임 기준

## Windows 사전 검사 결과

- `video/1.mp4`: 1274×720, 24 FPS, 544프레임, 약 22.7초
- `video/2.mp4`: 1280×720, 약 15 FPS, 640프레임, 약 42.5초
- `video/3.mp4`: 626×360, 24 FPS, 544프레임, 약 22.7초
- 최초 CPU PyTorch 빌드는 `c10.dll` 초기화 오류가 발생했지만 공식 `torch 2.5.1+cpu`로 교체한 뒤 모델 로드와 추론에 성공했습니다.
- 세 영상 모두에서 화재 또는 연기 박스가 검출됐습니다. 자세한 결과는 `MODEL_EVALUATION.md`를 확인합니다.
- `video/3.mp4`로 YOLO → WebSocket → Windows MJPEG → DB 이벤트 경로를 종단 간 검증했습니다.
- Windows CPU 측정 추론 속도는 약 13.6 FPS였으며 화재 이벤트가 `source=jetson-yolo`로 저장됐습니다.
- 최종 카메라와 CUDA 성능은 Jetson에서 검증해야 합니다.

검증하지 않은 항목을 작동 완료로 기록하지 않습니다.

