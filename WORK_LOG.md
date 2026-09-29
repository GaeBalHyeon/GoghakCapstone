# EV Fire Guard 로컬 재구성 작업 기록

## 1. PPT 분석 결과

PPT는 기존 건물 안전 관제 시스템을 전기차 주차장에 특화한 **EV Fire Guard**로 변경하는 내용을 담고 있습니다. 핵심 요구사항은 CCTV 기반 화재·연기 감지, 층·구역·충전기 위치 표시, 관리자 실시간 알림, 이벤트 로그와 스냅샷 기록입니다. 제안 구조는 CCTV 입력, Jetson 또는 PC의 YOLO 분석, 웹 서버와 DB, PC·모바일 관제 화면 순서입니다.

## 2. 기존 프로젝트에서 변경한 방향

| 기존 프로젝트 | 새 프로젝트 |
|---|---|
| 일반 건물 1~3층 화재·인원 관제 | 전기차 주차장 지하 1층 화재·연기 관제 |
| 인원 수와 카메라 신뢰도 중심 | 화재·연기 유형과 충전구역 중심 |
| AWS 서버와 MySQL | 로컬 FastAPI와 SQLite |
| Firebase 단말 토큰 직접 사용 | 브라우저 실시간 경보와 WebSocket |
| Jetson·카메라·mmWave 전제 | 장비 없는 4채널 시뮬레이션 기본 제공 |
| 여러 HTML 관리 화면 | 단일 관제 대시보드로 시연 흐름 단순화 |

## 3. 이번에 구현한 내용

- `re_capstone`에 기존 소스와 분리된 새 프로젝트 생성
- FastAPI REST API와 WebSocket 서버 구현
- 이벤트와 설정을 저장하는 SQLite 스키마 구현
- CAM-01~CAM-04의 화재·연기·정상 상태 시뮬레이션 구현
- 주차장 도면, 카메라 월, 요약 수치, 이벤트 로그 화면 구현
- 관리자 이벤트 확인·해제 기능 구현
- 자동 시뮬레이션 기능과 간격 설정 구현
- Windows용 설치 및 실행 PowerShell 스크립트 작성
- CMD 사용을 위한 `setup.bat`, `run.bat` 작성 및 기본 실행 안내 변경
- 관제 화면을 8pt 간격 체계와 단일 안전 오렌지 색상 기반으로 전면 재설계
- 고정 사이드바, 통합 상태 스트립, 주차장 도면, 테스트 제어부, 카메라 월과 이벤트 테이블의 정보 계층 정리
- 저대비 텍스트를 보정하고 키보드 포커스·반응형 레이아웃·200ms 마이크로 인터랙션 적용
- 이벤트 로그의 전체 기록 삭제 API와 확인창이 포함된 `기록 삭제` 버튼 추가
- 자동 시뮬레이션 기본값을 꺼짐으로 변경하고, 사용자가 켠 경우에만 작동하도록 재확인 로직 추가
- Jetson YOLO 영상과 이벤트를 Windows로 보내는 WebSocket 에이전트 추가
- Windows에 Jetson JPEG 수신, MJPEG 중계, 온라인 상태 표시 기능 추가
- SQLite 개발 모드와 로컬 MySQL 운영 모드를 선택할 수 있는 DB 연결 계층 추가
- GitHub 코드 공유와 공유기 런타임 통신의 역할을 `JETSON_HANDOFF.md`에 정리
- 로컬 Jetson 대체 클라이언트로 WebSocket 프레임, FPS, 화재 이벤트, DB 저장, 연결 해제를 통합 검증
- 테스트에서 발견한 WebSocket disconnect 반복 수신 예외 수정
- Jetson LAN 접속을 위해 서버 바인딩을 `127.0.0.1`에서 `0.0.0.0`으로 변경
- Windows 개인 네트워크 TCP 8000 방화벽 설정 스크립트와 네트워크 확인 스크립트 추가
- 이 PC의 MySQL 8.0 서비스 실행 상태와 MySQL CLI 설치 경로를 확인하고 CMD 초기화 스크립트 추가
- 확인 당시 Windows 유선 IP `192.168.1.138/24`, 게이트웨이 `192.168.1.1`을 인수인계 문서에 기록
- 원본 `best.pt`의 비실행 메타데이터 검사로 클래스 `{0: fire, 1: smoke}` 확인
- 확인된 모델을 `jetson_agent/best.pt`에 포함하고 SHA-256 해시 기록
- Jetson 서버 연결이 끊긴 동안 확정된 이벤트가 유실되지 않도록 대기 큐 추가
- 영상 파일 입력이 끝나면 처음부터 반복 재생하도록 Jetson 에이전트 보완
- Windows에서 테스트 영상 3개의 해상도, FPS, 프레임 수와 재생 시간 확인
- Windows CPU PyTorch의 `c10.dll` 초기화 오류를 확인해 실제 추론 검증 대상을 Jetson CUDA 환경으로 구분
- JetPack의 CUDA PyTorch와 OpenCV를 보존하는 `setup_jetson.sh` 추가
- CUDA, 카메라, 모델 클래스, Windows 서버 연결을 점검하는 `jetson_agent/diagnose.py` 추가
- 공식 CPU PyTorch 2.5.1로 모델 로드 및 테스트 영상 3개 실제 추론 성공
- 1초 간격 표본 평가에서 세 영상 모두 화재 또는 연기 검출 확인
- `video/3.mp4`를 사용해 YOLO 추론, JPEG WebSocket 전송, MJPEG 중계, 화재 이벤트 저장을 종단 간 검증
- 검증 시 Windows CPU에서 약 13.6 FPS, 화재 신뢰도 약 0.7499 확인
- 에이전트 종료 후 카메라 오프라인 전환과 테스트 이벤트 정리 확인
- 상세 결과를 `MODEL_EVALUATION.md`에 기록
- MySQL 관리자 비밀번호를 숨김 입력으로 받아 DB, 계정, 테이블, `.env`, 랜덤 Edge 토큰을 생성하는 `configure_windows.bat` 추가
- 기존 `.env` 자동 백업과 `.env.backup` Git 제외 처리
- MySQL insert/select/delete를 확인하고 테스트 행을 정리하는 `tests/mysql_integration.py` 추가
- 홈페이지 상단 운영 상태를 Jetson 연결, 시뮬레이션, 연결 대기 상태에 맞춰 동적으로 표시
- Windows `.env`, MySQL, 서버 포트, 모델, 영상, LAN 주소를 점검하는 `diagnose_windows.bat` 추가
- Windows 진단에서 실행 중인 FastAPI가 실제 MySQL 모드인지 `/api/health`로 검증하도록 보완

## 4. 장비가 없는 환경에서의 처리

현재 PC에서 CCTV 영상이나 센서 값을 허위로 실제 데이터처럼 표시하지 않았습니다. 모든 테스트 데이터는 화면에 `SIMULATED VIDEO`로 표시되며 이벤트 출처도 DB에 저장됩니다. 실제 장비가 준비되면 Jetson의 추론 결과를 `/api/detections`로 전송하도록 연결하면 됩니다.

PPT에 적힌 “20프레임 중 10회 이상 감지” 판정은 현재 `jetson_agent/agent.py`의 프레임 윈도우 로직으로 구현했습니다. 실제 카메라와 Jetson CUDA 환경에서의 최종 보정은 장비 연결 후 진행해야 합니다.

## 5. 다음 구현 순서

1. Jetson에 실제 카메라와 mmWave 센서를 연결합니다.
2. `diagnose.py`로 CUDA, 카메라, 모델, 서버 연결을 검증합니다.
3. 실제 주차장 환경에서 신뢰도와 20프레임 판정값을 보정합니다.
4. 카메라별 RTSP 주소와 도면 좌표를 설정 파일 또는 관리자 화면으로 이동합니다.
5. 텔레그램, 웹훅 또는 로컬 경광등 중 실제 사용할 알림 장치를 연동합니다.

## 6. 보안 정리

기존 프로젝트의 DB 비밀번호, 고정 IP, Firebase 서비스 계정과 FCM 토큰은 새 프로젝트로 복사하지 않았습니다. 외부 알림을 추가할 때는 `.env` 파일을 사용하고 Git에 포함하지 않아야 합니다.

## 7. 기존 `run_video` 폴더 분석 및 전환

- PT 파일 3개를 실제 로드하고 클래스와 SHA-256을 검사했습니다.
- `python/best.pt`는 `fire`, `smoke` 두 클래스로 학습된 커스텀 모델입니다.
- 두 `yolo11s.pt`는 SHA-256이 같은 동일 파일이며, 사람·자동차 등 COCO 80개 클래스용 기본 모델입니다.
- 프로젝트 목적과 다른 `3F-03.mp4`, `3F-07.mp4` 사무실 영상은 삭제했습니다.
- `3f03.py`, `3f07.py`는 AWS 전송/개별 FastAPI 방식 대신 공통 Jetson WebSocket 에이전트를 실행하도록 변경했습니다.
- 두 실행기의 기본 입력은 각각 카메라 장치 `0`, `1`이며 실제 감지 모델은 `python/best.pt`입니다.
- `url_parser.py`는 Cloudflare 주소 발급기 대신 로컬 서버와 카메라 상태 확인기로 변경했습니다.
- `영상 배포.bat`는 CMD에서 두 카메라 실행기를 시작하도록 변경했습니다.
- 더 이상 사용하지 않는 `cloudflared.exe`는 Git 업로드 대상에서 제외했습니다.

## 8. 실제 장비 연결 전 실행 경로 보강

- 기존 안내와 호환되도록 `start_server.bat`을 추가했으며 내부적으로 실제 서버 실행기인 `run.bat`을 호출합니다.
- Jetson `diagnose.py`가 HTTP 상태 확인뿐 아니라 `EDGE_TOKEN`을 사용한 실제 Edge WebSocket 인증 연결도 검사하도록 보강했습니다.
- 따라서 Jetson 에이전트를 실행하기 전에 카메라, CUDA, 모델, Windows 서버, 토큰 인증 문제를 한 번에 구분할 수 있습니다.

## 9. Windows 저장 영상과 Jetson 실시간 영상 분리

- `video/*.mp4`는 Windows FastAPI가 `/videos` 경로로 직접 제공합니다.
- 별도 저장 영상 플레이어 방식은 사용하지 않습니다.
- `CAM-01`은 Jetson 카메라에서 YOLO 처리한 실제 실시간 영상을 표시합니다.
- `CAM-02`, `CAM-03`, `CAM-04`는 Windows의 `1.mp4`, `2.mp4`, `3.mp4`를 각각 자동·무음·무한 반복해 실시간 관제 화면 형태로 표시합니다.
- 화면에는 영상 출처를 `Jetson YOLO` 또는 `Windows 로컬 관제 영상`으로 구분해 운영자가 실제 입력원을 알 수 있게 했습니다.
- 브라우저에서 세 로컬 영상의 `readyState=4`, `paused=false`, 해상도 인식을 확인해 실제 자동 재생 상태를 검증했습니다.

## 10. 통합 검사 안전성 보강

- `tests/edge_integration.py`가 `.env`의 `EDGE_TOKEN`을 읽어 인증이 설정된 실제 서버에서도 동작하도록 수정했습니다.
- `CAM-01`에는 로컬 영상이 없고 `CAM-02~04`에 `1.mp4~3.mp4`가 정확히 매핑되는지 검사합니다.
- 브라우저 재생에 필요한 MP4 Range 요청이 각 영상에서 `206 Partial Content`와 1,024바이트를 반환하는지 검사합니다.
- Jetson WebSocket 연결, JPEG 프레임, FPS, MySQL/SQLite 이벤트 저장, 연결 종료 상태를 함께 검사합니다.
- 검사로 생성한 이벤트는 해당 ID만 정리하므로 기존 사용자 기록을 삭제하지 않습니다.

## 11. 배치도 카메라 위치에 영상 통합

- 별도 실시간 카메라 관제 섹션을 삭제했습니다.
- 기존 주차장 배치도 위의 카메라 위치 표시를 실제 영상 패널로 교체했습니다.
- 배치도 `CAM-01` 위치는 Jetson 연결 시 YOLO 처리 MJPEG 영상을 표시하고, 미연결 시 `OFFLINE`을 표시합니다.
- 배치도 `CAM-02~04` 위치는 Windows의 `1.mp4~3.mp4`를 자동·무음·무한 반복합니다.
- 각 영상 패널을 누르면 기존 감지 테스트의 대상 카메라가 선택됩니다.
- 브라우저에서 배치도 상단과 하단을 확인해 네 영상 패널의 위치, 겹침, 자동 재생을 검증했습니다.


## 12. Windows MySQL 운영 모드 전환 (2026-09-29)

- MySQL 8 기본 인증 방식 때문에 PyMySQL 접속이 실패해 `cryptography==44.0.0`을 설치하고 `requirements.txt`에 추가했습니다.
- 관리자 CMD에서 TCP 8000 방화벽 규칙을 추가하고 `configure_windows.bat`으로 MySQL DB, 계정, 테이블, `.env`, `EDGE_TOKEN`을 생성했습니다.
- `run.bat` 실행 서버가 MySQL 모드(`/api/health` → `database: mysql`)로 동작함을 확인했습니다.
- `diagnose_windows.bat` 9/9 PASS, Edge 통합 검사와 MySQL 통합 검사 모두 통과했습니다.
- 남은 작업은 Jetson 실장 검증뿐입니다.

## 13. Jetson 실장 연결 (2026-09-29)

- 공유기 변경으로 Windows IP가 `192.168.0.223`이 되어 Jetson `.env`의 `WINDOWS_SERVER`를 이에 맞췄습니다.
- LAN 탐색으로 Jetson(`192.168.0.117`, Ubuntu 22.04 SSH)을 찾고 Windows 전용 SSH 키를 등록했습니다.
- Jetson의 기존 PyTorch는 cuDNN 8용 NVIDIA 빌드와 사용자 영역 CPU 빌드가 섞여 import가 실패하는 상태였습니다.
- 시스템 패키지를 건드리지 않도록 `~/evguard/venv`를 만들고 jetson-ai-lab `jp6/cu126`의 CUDA `torch 2.8.0`을 설치해 `CUDA True, GPU Orin`을 확인했습니다.
- `jetson_agent`를 `~/evguard/jetson_agent`로 복사했고 `best.pt` SHA-256 일치를 확인했습니다.
- `diagnose.py` 8/8 PASS (CUDA, 카메라 640x480, 모델 클래스, Windows 서버, Edge WebSocket).
- 에이전트가 서버 WebSocket ping에 응답하지 않아 약 40초마다 `Broken pipe`로 끊기는 문제를 발견해 `agent.py`에 수신 스레드를 추가했습니다.
- 수정 후 CAM-01 `edge_online=True`, 추론 약 27 FPS, 서버 MJPEG 약 7 FPS가 연속 유지되는 것을 확인했습니다.

## 14. Jetson 객체탐지 카메라 재가동 (2026-09-29)

- Windows 유선 LAN `192.168.0.223/24`, Jetson `192.168.0.201/24`, 게이트웨이 `192.168.0.1`로 동일 공유기 연결을 확인했습니다.
- Windows FastAPI 서버가 `0.0.0.0:8000`에서 이미 실행 중이며 `/api/health`가 MySQL 모드로 응답하는 것을 확인했습니다.
- Jetson `~/evguard/run_agent.sh`를 백그라운드로 실행해 카메라 `0`과 `best.pt` 화재·연기 YOLO 추론을 시작했습니다.
- Jetson 프로세스 PID는 실행 당시 `5293`이었으며 `CAM-01 edge_online=true`, 약 `29.9~30.0 FPS`를 확인했습니다.
- Windows `/api/video_feed/CAM-01`에서 `multipart/x-mixed-replace` 응답과 실제 연속 JPEG 프레임을 확인했습니다.
- 추가 유지 검사 후에도 프로세스와 영상 연결이 끊기지 않았습니다.
- 홈페이지는 일반 브라우저에서 `http://127.0.0.1:8000`으로 접속합니다.

## 15. 배치도 정렬·확대 화면·오경보 복구 개선

- 카메라 좌표를 네 주차 구역의 실제 중심 좌표에 맞게 조정하고 CSS 변수로 전달해 반응형 배치가 되도록 변경했습니다.
- 주차 구역 높이와 배치도 높이를 화면 크기에 맞춰 조정해 영상 패널이 구역 테두리 안에 들어가도록 했습니다.
- 각 카메라 패널을 클릭하거나 키보드로 선택하면 큰 화면 모달이 열리도록 구현했습니다.
- 이벤트 기록 삭제 시 모든 카메라의 일시 상태도 `normal`로 초기화하도록 서버를 수정했습니다.
- Jetson에서 화재·연기가 완전히 사라지면 `normal` 메시지를 Windows로 보내도록 에이전트를 수정했습니다.
- 활성 화재·연기 카메라가 없으면 홈페이지 경보 배너가 자동으로 닫히도록 수정했습니다.
- 필요한 후속 기능을 우선순위별로 `FEATURE_ROADMAP.md`에 정리했습니다.
