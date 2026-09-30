# EV Fire Guard 전체 프로젝트 인수인계

작성일: 2026-09-29  
프로젝트 경로: `C:\Users\Ria\Desktop\capstone\re_capstone`  
GitHub: `https://github.com/GaeBalHyeon/GoghakCapstone`  
기준 브랜치: `main`

이 문서는 Windows PC와 Jetson에서 후속 작업을 맡는 개발자 또는 Codex가 프로젝트의 목표, 현재 구현 상태, 시연 방법과 주요 파일을 한 번에 파악하기 위한 최종 인수인계 문서다. 비밀번호, Telegram 봇 토큰, MySQL 비밀번호와 Edge 인증 토큰은 기록하지 않는다.

## 1. 프로젝트 목표

EV Fire Guard는 전기차 충전 주차장에서 발생하는 화재와 연기를 조기에 감지하고 초기 대응까지 지원하는 로컬 모빌리티 안전 관제 시스템이다.

핵심 목표는 다음과 같다.

1. Jetson에 연결된 카메라 영상을 YOLO로 실시간 분석한다.
2. 화재 또는 연기가 일정 시간 지속될 때만 확정해 순간 오탐을 줄인다.
3. AI 박스가 표시된 영상을 같은 공유기의 Windows 관제 홈페이지에서 실시간으로 본다.
4. 이벤트 발생 순간의 스냅샷, 위치, 신뢰도와 처리 상태를 MySQL에 저장한다.
5. 관리자 휴대폰으로 Telegram 경보를 빠르게 전송한다.
6. 화재가 확정되면 해당 구역 충전기를 긴급 차단한 것처럼 시뮬레이션하고 대응시간을 수치로 증명한다.
7. 인터넷이 없어도 영상 분석, 홈페이지, DB와 로컬 경보 기능이 동작하도록 구성한다. Telegram만 외부 인터넷이 필요하다.

발표에서는 단순 CCTV가 아니라 다음 흐름을 갖는 **전기차 충전시설 능동형 모빌리티 안전 플랫폼**으로 설명한다.

```text
화재·연기 감지 → 3초 지속 확인 → 이벤트 확정 → 스냅샷 저장
→ 가상 충전 차단 → 홈페이지 경보 → Telegram 알림 → 관리자 확인·복구
```

## 2. 전체 시스템 구조

```text
Jetson Orin Nano Super
  USB 카메라 / OpenCV / best.pt YOLO
  └─ 박스 표시 JPEG + FPS + 확정 이벤트
                      │ WebSocket / 같은 공유기
                      ▼
Windows PC
  FastAPI + MySQL 8.0 + 영상 중계 + 이벤트/스냅샷 저장
                      │ HTTP / WebSocket
                      ▼
PC·모바일 웹 관제 화면 + Telegram 휴대폰 경보
```

- Jetson: 카메라 입력과 YOLO 추론 담당
- Windows: 웹 서버, MySQL, 영상 중계, 이벤트 기록, Telegram 담당
- 브라우저: Windows의 `8000` 포트에 접속
- GitHub: 소스와 문서 공유
- 공유기: 실행 중 영상과 이벤트 전달. 파일 동기화 용도가 아님

## 3. 현재 작동 상태

2026-09-29 최종 확인 상태:

| 항목 | 상태 |
|---|---|
| Windows FastAPI | 정상, `0.0.0.0:8000` |
| DB | MySQL, `/api/health` 정상 |
| Jetson CAM-01 | 온라인, 유선 `192.168.0.223:8000` 연결 |
| Jetson YOLO | 화재 감지만 활성화, 약 25~30 FPS 수신 확인 |
| Windows 로컬 영상 | CAM-02~04 자동·무음·무한 반복 |
| Telegram | 설정 및 실제 수신 확인 |
| 자동 시뮬레이션 | 기본 OFF |
| Jetson 자동 실행 | 사용자 crontab 등록 완료 |
| Windows 원클릭 실행 | 구현 완료 |
| 가상 충전 차단 | 구현 완료 |
| GitHub 기준 커밋 | `691af68` 이상 |

현재 Windows는 유선 `192.168.0.223`으로 Jetson 공유기에, Wi-Fi `192.168.29.58`로 인터넷에 연결되어 있다. 다중 네트워크에서 `.local` 이름 해석이 불안정해 Jetson의 `WINDOWS_SERVER`는 `192.168.0.223:8000`으로 설정했다. 유선 공유기가 바뀌면 이 주소를 다시 확인해야 한다.

## 4. 현재 구현된 기능

### AI와 영상

- Jetson USB 카메라 실시간 입력
- `best.pt` YOLO 화재·연기 탐지
- 모델 클래스 `{0: fire, 1: smoke}`
- 화재·연기 바운딩 박스가 포함된 JPEG를 Windows로 전송
- Jetson 영상의 FPS와 온라인 상태 표시
- 카메라 클릭 시 큰 화면 dialog 표시
- CAM-02~04의 Windows 저장 영상을 실시간 관제처럼 자동·무음·무한 반복
- 영상 플레이어 컨트롤, 우클릭과 임의 일시정지 방지
- PC와 모바일에서 2×2 카메라 배치 유지

### 판정과 경보

- 기본 3초 동안 화재·연기가 유지돼야 확정
- 현재 시연 Jetson은 `.env`의 `SMOKE_DETECTION=0`으로 연기 감지를 끄고 화재 클래스만 사용
- 최대 0.6초의 짧은 검출 누락 허용
- 2초 동안 감지가 사라지면 정상 복귀
- 화재는 빨간색, 연기는 주황색 테두리
- 브라우저 경보 배너와 경보음
- 정상 상태에서는 허위 경보 배너를 표시하지 않음

### 이벤트와 스냅샷

- 이벤트 발생 시 MySQL `events` 테이블 저장
- 카메라, 층, 구역, 충전기, 유형, 신뢰도, 출처와 시각 기록
- 감지 순간 Jetson 프레임을 스냅샷으로 저장
- 홈페이지 이벤트 기록에서 스냅샷 확대
- 관리자 `확인·해제`
- 이벤트 전체 삭제 및 스냅샷 파일 정리
- 오늘의 전체 감지, 화재/연기, 처리율과 평균 확인시간 표시
- 카메라별·유형별 막대그래프

### Telegram 외부 알림

- 확정 즉시 텍스트 경보를 먼저 전송
- 스냅샷은 다음 메시지로 별도 전송
- 네트워크 오류, HTTP 429 또는 5xx는 2초·5초 간격으로 최대 3회 재시도
- 전송 성공·실패 상태를 DB와 홈페이지에 반영
- Jetson 카메라가 기본 10초 이상 끊기면 끊김 알림
- 카메라 재연결 시 복구 알림
- Telegram은 외부 인터넷이 있어야 작동하지만 나머지 로컬 관제 기능은 인터넷 없이 작동

### 가상 긴급 충전 차단

- 화재 확정 시 관할 충전구역에 약 180ms의 가상 제어기 응답 수행
- CAM-01 → `A-01~A-04`
- CAM-02 → `B-01~B-04`
- CAM-03·04 → 충전기 없음, 차단 대상 아님
- 시스템 패널에 `충전 가능` 또는 `차단 완료 · Nms` 표시
- 이벤트 DB에 차단 요청·완료 시각, 처리시간과 상태 저장
- 경보 배너, 이벤트 기록, 오늘 평균 차단 응답시간과 Telegram에 결과 표시
- 모든 화면에서 `SIMULATION`을 표시해 실제 전원 제어와 구분
- 관리자 확인·해제 또는 정상 복귀 시 다시 `충전 가능`

실제 OCPP 충전기가 연결되면 `app/main.py`의 가상 차단 부분을 원격 정지 명령으로 교체할 수 있다.

### 자동화와 보안

- Windows 원클릭 BAT가 MySQL 확인, 현재 LAN IP 반영, 서버 실행과 브라우저 열기를 처리
- 이미 서버가 실행 중이면 중복 서버를 만들지 않고 홈페이지만 열음
- Jetson은 재부팅 20초 후 자동 실행되고 비정상 종료 시 5초 뒤 재시작
- Jetson 인증값을 URL이 아닌 `Authorization` 헤더로 전송해 서버 로그 노출 방지
- `.env`, DB 비밀번호와 토큰은 Git에서 제외

## 5. 시연에 사용하는 파일과 경로

### 가장 중요한 실행 파일

| 용도 | Windows 절대 경로 |
|---|---|
| 바탕화면 원클릭 실행 | `C:\Users\Ria\Desktop\EV_Fire_Guard_START.bat` |
| 저장소 내부 원클릭 실행 | `C:\Users\Ria\Desktop\capstone\re_capstone\START_EV_FIRE_GUARD.bat` |
| 일반 서버 실행 | `C:\Users\Ria\Desktop\capstone\re_capstone\run.bat` |
| Windows 종합 진단 | `C:\Users\Ria\Desktop\capstone\re_capstone\diagnose_windows.bat` |
| 네트워크 주소 확인 | `C:\Users\Ria\Desktop\capstone\re_capstone\network_check.bat` |
| 유선 Jetson + Wi-Fi 인터넷 동시 사용 | `C:\Users\Ria\Desktop\capstone\re_capstone\fix_dual_network.bat` |
| Telegram 최초/재설정 | `C:\Users\Ria\Desktop\capstone\re_capstone\configure_telegram.bat` |
| GitHub 업로드 | `C:\Users\Ria\Desktop\capstone\re_capstone\push.bat` |

### 시연 영상

| 카메라 | 파일 | 홈페이지 용도 |
|---|---|---|
| CAM-01 | Jetson USB 카메라 | 실시간 YOLO 영상 |
| CAM-02 | `C:\Users\Ria\Desktop\capstone\re_capstone\video\1.mp4` | Windows 반복 영상 |
| CAM-03 | `C:\Users\Ria\Desktop\capstone\re_capstone\video\2.mp4` | Windows 반복 영상 |
| CAM-04 | `C:\Users\Ria\Desktop\capstone\re_capstone\video\3.mp4` | Windows 반복 영상 |

### YOLO 모델

- 실제 화재·연기 학습 모델: `C:\Users\Ria\Desktop\capstone\re_capstone\jetson_agent\best.pt`
- 원본 호환 사본: `C:\Users\Ria\Desktop\capstone\re_capstone\run_video\python\best.pt`
- 모델 크기: 19,167,642 bytes
- SHA-256: `331E95833A3E7E865C8F7F846585561084F1159FB9443834A786AF2C22CB6FC8`
- `yolo11s.pt` 두 파일은 COCO 기본 모델이며 화재 학습 모델이 아니므로 실제 시연에 사용하지 않는다.

### 웹과 서버 코드

| 영역 | 경로 |
|---|---|
| FastAPI/API/WebSocket | `app\main.py` |
| MySQL·SQLite 계층 | `app\database.py` |
| Telegram 전송·재시도 | `app\notifications.py` |
| 홈페이지 HTML | `static\index.html` |
| 홈페이지 동작 | `static\app.js` |
| 반응형 디자인 | `static\style.css` |
| Jetson YOLO 에이전트 | `jetson_agent\agent.py` |
| Jetson 진단 | `jetson_agent\diagnose.py` |
| Jetson 자동 실행 래퍼 | `jetson_agent\autostart_agent.sh` |

### 관련 자료와 문서

- 최초 기획 PPT: `C:\Users\Ria\Desktop\전기차_주차장_화재감지_PPT_1.pptx`
- 전체 작업 기록: `WORK_LOG.md`
- 이 최종 인수인계: `PROJECT_HANDOFF.md`
- Jetson 세부 인수인계: `JETSON_HANDOFF.md`
- 모델 검증 결과: `MODEL_EVALUATION.md`
- 기능 로드맵: `FEATURE_ROADMAP.md`
- 기존 영상 배포 구조 설명: `run_video\README.md`

## 6. 시연 당일 실행 순서

### 사전 준비

1. Windows PC와 Jetson을 같은 공유기에 연결한다.
2. 가능하면 둘 다 유선 LAN을 사용한다.
3. Windows 네트워크 프로필이 `개인`인지 확인한다.
4. Jetson 카메라 연결과 전원을 확인한다.
5. Telegram까지 시연할 경우 공유기에 외부 인터넷이 연결되어 있는지 확인한다.

### 실행

Windows 바탕화면에서 다음 파일을 더블클릭한다.

```text
C:\Users\Ria\Desktop\EV_Fire_Guard_START.bat
```

정상 출력 예시:

```text
[NETWORK] Windows LAN address: ...
[READY] Windows server and Telegram configuration loaded.
[READY] Jetson connects using DESKTOP-TCULRT5.local:8000.
[OPEN] http://현재_PC_IP:8000
Uvicorn running on http://0.0.0.0:8000
```

열린 CMD 창은 시연 중 닫지 않는다. 브라우저가 자동으로 열리지 않으면 PC에서 `http://127.0.0.1:8000`, 휴대폰에서는 BAT에 출력된 `http://PC_IP:8000`으로 접속한다.

Jetson은 전원을 켜면 자동 실행된다. 약 20초 후 홈페이지 CAM-01에 `JETSON LIVE`가 표시되는지 확인한다.

### 권장 시연 시나리오

1. 정상 상태의 4개 카메라와 시스템 상태 패널을 보여준다.
2. CAM-01의 Jetson 실시간 YOLO 영상과 FPS를 설명한다.
3. 우측 상단 `감지 테스트`를 누른다.
4. CAM-01을 선택하고 `화재`를 누른다.
5. 빨간 카메라 테두리와 경보 배너를 보여준다.
6. `A-01~A-04 가상 긴급 차단 완료`와 약 180ms 응답시간을 보여준다.
7. 이벤트 기록의 스냅샷, 신뢰도, 충전 안전 제어와 Telegram 전송 완료를 보여준다.
8. 휴대폰 Telegram의 화재·위치·차단 알림과 스냅샷을 보여준다.
9. 오늘의 관제 요약에서 평균 차단 응답시간을 보여준다.
10. `확인·해제`를 눌러 카메라와 충전구역이 정상으로 복구되는 것을 보여준다.

주의: 감지 테스트의 화재 버튼은 실제 Telegram 메시지를 보낸다. 발표 전에 테스트 기록을 지우고 휴대폰 알림 상태를 확인한다.

실제 Jetson YOLO 감지는 화재·연기가 3초간 지속돼야 확정된다. 홈페이지의 수동 감지 테스트 버튼은 발표 흐름을 빠르게 검증하기 위해 즉시 이벤트를 만든다.

## 7. CMD 점검 명령

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone
diagnose_windows.bat
network_check.bat
```

서버 직접 실행:

```bat
START_EV_FIRE_GUARD.bat
```

API 확인:

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/cameras
http://127.0.0.1:8000/api/events
http://127.0.0.1:8000/api/charging-controls
http://127.0.0.1:8000/docs
```

자동화 검사:

```bat
.venv\Scripts\python.exe tests\mysql_integration.py
.venv\Scripts\python.exe tests\notification_retry.py
```

`tests\edge_integration.py`는 가짜 CAM-01 에이전트를 사용하므로 실제 Jetson 에이전트가 실행 중일 때는 함께 실행하지 않는다.

## 8. Jetson 정보와 점검

- 장비: Jetson Orin Nano Super
- OS: Ubuntu 22.04 / JetPack 6 / L4T R36.4.7
- 설치 경로: `~/evguard/jetson_agent`
- 가상환경: `~/evguard/venv`
- 로그: `~/evguard/agent.log`
- 카메라: 기본 `/dev/video0`
- Windows 서버 주소: `DESKTOP-TCULRT5.local:8000`
- 인증: Windows와 Jetson `.env`의 `EDGE_TOKEN`이 같아야 함

Jetson 점검:

```bash
cd ~/evguard/jetson_agent
source ~/evguard/venv/bin/activate
export PYTHONNOUSERSITE=1
python diagnose.py
tail -f ~/evguard/agent.log
crontab -l
```

자동 실행 등록은 이미 했지만 새 Jetson에서는 다음을 한 번 실행한다.

```bash
cd ~/evguard/jetson_agent
chmod +x install_autostart.sh autostart_agent.sh
./install_autostart.sh
```

Jetson 전용 CUDA PyTorch를 일반 PyPI CPU 패키지로 덮어쓰면 안 된다. 세부 설치 이력은 `JETSON_HANDOFF.md`를 확인한다.

## 9. 네트워크와 외부 인터넷

로컬에서 인터넷 없이 가능한 기능:

- Jetson YOLO 추론
- Jetson → Windows 영상 전송
- 홈페이지 실시간 관제
- MySQL 이벤트 저장
- 스냅샷 저장
- 가상 충전 차단
- 브라우저 경보

인터넷이 필요한 기능:

- Telegram 메시지와 스냅샷 전송
- GitHub pull/push
- 최초 패키지 설치

새 시연장에서 공유기가 바뀌면 PC와 Jetson IP가 달라질 수 있다. 인터넷 없는 유선 공유기와 인터넷 Wi-Fi를 함께 쓸 때는 관리자 권한으로 `fix_dual_network.bat`을 실행한다. 이 도구는 Wi-Fi 메트릭을 10, 유선 메트릭을 80으로 지정해 인터넷은 Wi-Fi로 보내고 Jetson의 로컬 대역은 유선으로 유지한다.

연결되지 않을 때 확인 순서:

1. Windows BAT에 표시되는 LAN IP 확인
2. Windows 네트워크 프로필을 `개인`으로 변경
3. Windows와 Jetson이 같은 IP 대역인지 확인
4. Jetson `.env`의 `WINDOWS_SERVER`를 Windows 유선 IP로 설정
5. Jetson에서 `curl http://WINDOWS_유선_IP:8000/api/health`
6. `.env`의 `EDGE_TOKEN` 일치 확인
7. `~/evguard/agent.log` 확인

## 10. 데이터와 비밀정보

- Windows 설정: 프로젝트 루트 `.env`
- Jetson 설정: `~/evguard/jetson_agent/.env`
- 스냅샷: Windows `data\snapshots\`
- 운영 이벤트: MySQL DB `ev_fire_guard`, 테이블 `events`
- SQLite는 개발 대체 백엔드로만 유지

다음 값은 GitHub, 문서와 채팅에 올리지 않는다.

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `EDGE_TOKEN`
- RTSP 사용자명과 비밀번호

토큰이 로그나 화면에 노출되면 Windows와 Jetson 양쪽 값을 함께 교체하고 두 프로세스를 재시작한다.

## 11. 알려진 제한사항

- 차량 객체 탐지와 번호판 인식은 현재 구현하지 않았다.
- 실제 충전기 전원 차단은 하지 않으며 `SIMULATION`이다.
- mmWave 센서는 현재 연결하지 않았다.
- Telegram은 외부 인터넷이 없으면 실패하지만 로컬 시스템은 계속 동작한다.
- 실제 화재 환경 검증이 아니라 학습 모델과 안전한 테스트 영상 중심으로 검증했다.
- CAM-02~04는 실제 카메라가 아니라 Windows MP4 반복 영상이다.
- 사용자 로그인과 권한 분리는 아직 없다.
- 이벤트 검색, 필터, CSV 내보내기와 자동 보관기간 정리는 아직 없다.

## 12. 권장 후속 작업

모빌리티 경진대회 관점의 권장 순서:

1. 같은 화재의 중복 이벤트를 막는 카메라별 재알림 대기시간
2. 이벤트 검색·필터와 CSV 시연 보고서 출력
3. 스냅샷 보관기간과 디스크 용량 자동 정리
4. 실제 OCPP 충전기 또는 테스트 제어기 연동
5. 충전 상태·온도 데이터를 결합한 위험 점수
6. 화재 위치 기반 안전 출차·대피 경로 표시
7. mmWave 사람 존재 정보 결합
8. 다중 Jetson·다중 층 지원

실제 충전기 연동 전에는 홈페이지와 발표에서 항상 가상 차단임을 명시한다.

## 13. GitHub 작업 규칙

Windows에서 변경 내용을 올릴 때:

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone
push.bat
```

Jetson에서 최신 코드 받기:

```bash
cd ~/GoghakCapstone
git pull origin main
```

Jetson의 실제 설치 폴더가 `~/evguard`이므로 Git 저장소와 실행 폴더가 다르면 변경된 `jetson_agent` 파일을 실행 폴더에 반영해야 한다.

작업 시작 전 확인:

```text
git status
git log -5 --oneline
```

기존 사용자 변경은 임의로 삭제하거나 초기화하지 않는다. `.env`, 스냅샷과 DB 파일을 커밋하지 않는다.

## 14. 문서 우선순위

후속 작업자는 다음 순서로 읽는다.

1. `PROJECT_HANDOFF.md` — 현재 전체 상태와 시연
2. `WORK_LOG.md` — 지금까지의 세부 작업 이력
3. `JETSON_HANDOFF.md` — Jetson과 네트워크 상세
4. `README.md` — 설치와 일반 사용법
5. `MODEL_EVALUATION.md` — 모델과 영상 평가
6. `FEATURE_ROADMAP.md` — 후속 기능 후보

`CURRENT_HANDOFF.md`와 `handoff/AI_HANDOFF_2026-09-29.md`에는 초기 단계의 정보가 일부 남아 있으므로, 상충하는 내용이 있으면 이 문서와 최신 Git 커밋을 우선한다.

## 15. 인수인계 직전 최종 확인 결과

- Windows `/api/health`: `status=ok`, `database=mysql`
- CAM-01: `edge_online=true`, 약 `30 FPS`
- 바탕화면 원클릭 실행 파일 존재 확인
- 가상 충전 차단 DB 컬럼 자동 마이그레이션 확인
- Python 컴파일 검사 통과
- JavaScript 문법 검사 통과
- Telegram 재시도·전송 순서 검사 통과
- 최신 기능 커밋 `691af68`이 GitHub `main`에 반영됨

이 문서를 수정할 때는 실제로 확인한 상태와 예상 상태를 구분해 기록한다. 검증하지 않은 기능을 완료로 표시하지 않는다.
