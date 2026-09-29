# AI 작업자용 인수인계 (2026-09-29 세션)

이 문서는 다음 AI 작업자가 바로 이어서 작업할 수 있도록 이번 세션의 결과, 현재 상태, 작업 방법, 주의점을 정리한 것이다. 프로젝트 전체 설명은 `../CURRENT_HANDOFF.md`, 전체 이력은 `../WORK_LOG.md`를 함께 본다.

## 1. 프로젝트 한 줄 요약

EV Fire Guard: 전기차 주차장 화재·연기 관제. Jetson이 USB 카메라 영상을 YOLO(`best.pt`, 클래스 `{0: fire, 1: smoke}`)로 추론해 박스가 그려진 JPEG와 확정 이벤트를 WebSocket으로 Windows FastAPI 서버에 보내고, 서버는 MySQL에 이벤트를 저장하며 홈페이지 배치도 CAM-01에 실시간 영상을 띄운다. CAM-02~04는 Windows `video/1.mp4~3.mp4`를 반복 재생한다.

## 2. 현재 상태 (세션 종료 시점)

| 항목 | 상태 |
|---|---|
| Windows 서버 | `run.bat`로 `0.0.0.0:8000` 실행 중, `/api/health` → `database: mysql` |
| Windows 진단 | `diagnose_windows.bat` 9/9 PASS |
| 통합 검사 | `tests\edge_integration.py`, `tests\mysql_integration.py` 모두 통과 |
| 방화벽 | TCP 8000 인바운드 허용 규칙(개인 프로필) 추가됨 |
| 네트워크 프로필 | 사용자가 "개인"으로 변경함 (공용이면 Jetson 접속 불가) |
| Jetson 진단 | `diagnose.py` 8/8 PASS |
| Jetson 에이전트 | 백그라운드 실행 중, CAM-01 `edge_online=True`, 추론 약 27 FPS, 서버 MJPEG 약 7 FPS, 1분 이상 끊김 없음 |

## 3. 환경 정보

### Windows PC
- 경로: `C:\Users\Ria\Desktop\capstone\re_capstone`
- Python 가상환경: `.venv\Scripts\python.exe` (Python 3.12)
- LAN IP: `192.168.0.223` (이전 공유기에서는 `192.168.1.138`였음. 공유기가 바뀌면 달라진다)
- MySQL80 서비스, DB `ev_fire_guard`, 앱 계정 `evguard` (비밀번호와 `EDGE_TOKEN`은 `.env`에 있음, Git 제외)
- Git은 PATH에 없다. 사용 경로: `C:\Users\Ria\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe`
- GitHub: `https://github.com/GaeBalHyeon/GoghakCapstone` (`main`, 마지막 푸시 커밋 `1a20eb3`)

### Jetson
- 장비: Jetson Orin Nano Engineering Reference Developer Kit Super
- OS: Ubuntu 22.04, L4T R36.4.7 (JetPack 6), CUDA 12.6, cuDNN 9.3, TensorRT 10.3, Python 3.10
- IP: `192.168.0.117` (서버 로그에는 Jetson이 `192.168.0.201`로도 보인다. 인터페이스가 2개인 것으로 보임)
- 계정: `pangsu` (sudo는 비밀번호 필요, 비밀번호는 모른다)
- 카메라: `/dev/video0`(사용 중, 640x480), `/dev/video1`
- 설치 위치: `~/evguard/`
  - `jetson_agent/` : `agent.py`, `diagnose.py`, `best.pt`, `.env`(권한 600) 등
  - `venv/` : 전용 가상환경
  - `run_agent.sh` / `stop_agent.sh` / `agent.log`
  - `install_env.sh`, `fix_torch.sh` 및 로그 : 설치 때 쓴 스크립트
- Jetson `.env` 값: `WINDOWS_SERVER=192.168.0.223:8000`, `EDGE_TOKEN`=Windows `.env`와 동일, `CAMERA_ID=CAM-01`, `CAMERA_SOURCE=0`, `MODEL_PATH=best.pt`, `CONFIDENCE=0.45`, `TARGET_FPS=8`, `WINDOW_SIZE=20`, `MIN_DETECTIONS=10`
- 홈 폴더에 예전 `capstone.service`(disabled, inactive)와 cloudflared 흔적이 있다. 현재 구조와 무관하니 건드리지 않았다.

## 4. 이번 세션에서 한 일

1. Windows 상태 점검: 통합 검사는 통과, 진단은 `.env` 없음으로 5/8.
2. MySQL 구성: `configure_windows.bat` 실행 중 `cryptography` 누락 오류(MySQL 8 `caching_sha2_password`) → 설치 후 `requirements.txt`에 `cryptography==44.0.0` 추가. 사용자가 root 비밀번호를 입력해 `.env` 생성 완료.
3. 방화벽 8000 규칙 추가(관리자 권한, 사용자가 UAC 승인).
4. 공유기 변경 확인 → PC IP `192.168.0.223`, LAN 스캔으로 Jetson `192.168.0.117` 발견, 네트워크 프로필 "개인"으로 변경(사용자).
5. SSH 키 등록: Windows에 `C:\Users\Ria\.ssh\evguard_jetson` 생성, 사용자가 비밀번호를 입력해 Jetson `~/.ssh/authorized_keys`에 등록(주석 `ria-pc-evguard`).
6. Jetson PyTorch 문제 해결:
   - 기존 상태: `/usr/local/.../dist-packages`에 NVIDIA `torch 2.4.0a0 nv24.7`(cuDNN 8 필요), `~/.local`에 CPU `torch 2.12.0`이 섞여 있고, `libcudnn.so.8`이 cuDNN 9를 가리키는 심볼릭 링크로 억지 연결되어 import 실패.
   - 조치: 시스템·사용자 패키지는 건드리지 않고 `~/evguard/venv` 생성, `PYTHONNOUSERSITE=1`로 `~/.local` 격리.
   - 설치: `numpy==1.26.4`, `ultralytics==8.3.0`, `opencv-python-headless==4.10.0.84`, `websocket-client==1.8.0`, `python-dotenv==1.0.1`, 그리고 `https://pypi.jetson-ai-lab.io/jp6/cu126`의 `torch==2.8.0`, `torchvision==0.23.0`.
   - 결과: `CUDA True`, `GPU Orin`, CUDA NMS 동작 확인.
7. `jetson_agent` 파일 복사(scp), `best.pt` SHA-256 `331e9583...cb6fc8` 일치 확인.
8. `diagnose.py` 8/8 PASS.
9. 버그 수정 `jetson_agent/agent.py`: 서버(uvicorn)가 WebSocket ping을 보내는데 에이전트가 수신을 안 해서 pong이 없고, 약 40초마다 `[Errno 32] Broken pipe`로 끊겼다. `drain_incoming` 수신 스레드를 추가하고 `enable_multithread=True`, `settimeout(None)`으로 연결하도록 변경. Jetson에도 반영 후 재시작.
10. 안정성 확인: 20초 간격 4회 측정 모두 `online=True`, 5초당 MJPEG 35~36프레임.
11. `CURRENT_HANDOFF.md`, `WORK_LOG.md`(12·13절) 갱신.

## 5. 커밋되지 않은 변경

- `requirements.txt` (`cryptography==44.0.0` 추가)
- `jetson_agent/agent.py` (WebSocket 수신 스레드)
- `CURRENT_HANDOFF.md`, `WORK_LOG.md`
- `handoff/AI_HANDOFF_2026-09-29.md` (이 문서)

사용자가 요청하기 전에는 커밋·푸시하지 않는다. `.env`가 스테이징되지 않도록 파일을 지정해서 add한다.

## 6. 남은 작업 (우선순위 순)

1. 실제 화재·연기 이벤트 저장 확인: 카메라에 화재 영상(휴대폰 등)을 비추고 20프레임 중 10회 이상 감지되면 이벤트가 MySQL `events`에 `source=jetson-yolo`로 저장되는지 `/api/events`로 확인한다. 아직 검증하지 않았다.
2. Jetson 재부팅 시 자동 실행: 현재는 수동 실행(`setsid nohup`)이라 재부팅하면 꺼진다. systemd user 서비스(`systemctl --user` + `loginctl enable-linger`, 후자는 sudo 필요) 또는 사용자에게 sudo 비밀번호 입력을 요청해 system 서비스로 등록한다.
3. `EDGE_TOKEN` 로그 노출: uvicorn 접근 로그에 `/ws/edge/CAM-01?token=...`이 그대로 찍힌다. 토큰을 헤더로 옮기거나 로그에서 마스킹하는 개선을 검토한다(서버 `app/main.py`의 `edge_websocket`, 에이전트 `connect_websocket` 양쪽 수정 필요).
4. `setup_jetson.sh` 갱신: 현재 스크립트는 시스템 PyTorch를 전제로 해서 이 Jetson에서는 실패한다. 이번에 쓴 venv 방식(jp6/cu126 인덱스)으로 바꾸면 재설치가 쉬워진다.
5. 빈 임시 폴더 `re_capstone\kiro_tmp` 삭제(프로세스 점유로 지우지 못함).
6. 필요 시 Windows 쪽 CAM-01 외 추가 Jetson 카메라(`/dev/video1`) 연동.

## 7. 다른 AI가 작업할 때의 요령과 함정

### 터미널 출력
- 이 환경의 PowerShell 도구는 명령을 한 글자씩 에코해서 출력이 깨지고, 실제 결과가 안 보이는 경우가 많다. 결과는 항상 파일로 저장한 뒤 파일 읽기 도구로 확인한다.
- `$env:TEMP`에 쓴 파일은 보이지 않은 적이 있다. 작업 폴더 안에 임시 폴더를 만들어 쓰고 끝나면 지운다.
- `cmd /c`의 한글 출력은 CP949라 깨진다. Python으로 `decode("cp949")` 하거나 UTF-8로 저장한다.
- 배치 파일 안의 긴 PowerShell 한 줄, `timeout` 명령은 깨지거나 동작하지 않았다. 복잡한 로직은 `.py` 스크립트로 작성한다.
- 서버처럼 오래 도는 명령은 백그라운드 프로세스 도구로 실행한다. 이미 8000 포트에 서버가 떠 있으면 새 서버는 `10048` 오류로 죽는다.

### Jetson 원격 실행
- 키 인증으로 비밀번호 없이 접속된다.
  ```powershell
  ssh -i "$env:USERPROFILE\.ssh\evguard_jetson" -o BatchMode=yes pangsu@192.168.0.117 "명령"
  ```
- 로컬 bash 스크립트를 보낼 때는 CRLF 때문에 `$'\r': command not found`가 난다. `"tr -d '\r' | bash -s"`로 받거나 LF로 변환해 보낸다.
- 오래 걸리는 설치는 Jetson에서 `nohup ... > log 2>&1 &`로 돌리고 로그를 주기적으로 `tail`한다.
- 에이전트 제어: `~/evguard/run_agent.sh` 실행은 `setsid nohup ~/evguard/run_agent.sh > ~/evguard/agent.log 2>&1 < /dev/null &`, 중지는 `~/evguard/stop_agent.sh`.
- venv 명령은 반드시 `source ~/evguard/venv/bin/activate; export PYTHONNOUSERSITE=1` 후 실행한다. 시스템 `python3`는 PyTorch import가 실패한다.
- `pip install` 시 PyPI를 extra index로 같이 주면 CPU `torch 2.8.0+cpu`가 선택된다. CUDA torch는 `--index-url https://pypi.jetson-ai-lab.io/jp6/cu126`만 지정하고 `--no-deps`로 설치한다.
- Jetson의 시스템 PyTorch, `~/.local` 패키지, `libcudnn.so.8` 링크는 수정하지 않았다. 사용자 동의 없이 건드리지 않는다.

### 사용자 입력이 필요한 것
- MySQL root 비밀번호, Jetson 로그인/sudo 비밀번호, UAC 승인, 네트워크 프로필 변경은 AI가 할 수 없다. 필요한 창을 띄우고 사용자에게 입력을 요청한다. 비밀번호는 채팅에 적지 말라고 안내한다.
- 사용자는 한국어로 대화하며, 설명은 쉬운 단계별 안내를 선호한다.

## 8. 빠른 점검 명령

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone
run.bat
diagnose_windows.bat
.venv\Scripts\python.exe tests\edge_integration.py 8000
.venv\Scripts\python.exe tests\mysql_integration.py
```

주의: `tests\edge_integration.py`는 가짜 CAM-01 에이전트로 접속한다. 실제 Jetson 에이전트가 연결된 상태에서 돌리면 CAM-01 상태가 섞이므로 Jetson 에이전트를 잠시 멈추고 실행한다.

Jetson 쪽:

```bash
source ~/evguard/venv/bin/activate && export PYTHONNOUSERSITE=1
cd ~/evguard/jetson_agent && python diagnose.py
tail -f ~/evguard/agent.log
```

서버에서 CAM-01 상태: `http://127.0.0.1:8000/api/cameras` (`edge_online`, `fps`), 영상: `http://127.0.0.1:8000/api/video_feed/CAM-01`, 이벤트: `http://127.0.0.1:8000/api/events`
