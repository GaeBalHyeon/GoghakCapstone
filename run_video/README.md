# 기존 영상 배포 폴더 전환 기록

이 폴더는 기존 AWS/Cloudflare 영상 배포 코드를 현재 로컬 시스템에 맞게 바꾼 호환 실행 폴더다.

## 모델 판별 결과

- `python/best.pt`: 커스텀 학습 모델. 클래스는 `fire`, `smoke`다.
- `yolo11s.pt`, `python/yolo11s.pt`: 서로 해시가 같은 Ultralytics COCO 범용 모델이다. 사람·자동차 등 80개 클래스를 인식하며 화재 학습 모델이 아니다.
- 실제 화재 감지 실행에는 `python/best.pt`만 사용한다.

## 변경된 구조

- AWS 고정 IP와 HTTP 이벤트 전송을 제거했다.
- Cloudflare 임시 터널과 카메라별 FastAPI 서버를 제거했다.
- 공통 `jetson_agent/agent.py`가 YOLO 추론, 바운딩 박스 영상, 감지 이벤트를 Windows 서버로 WebSocket 전송한다.
- `3f03.py`는 `CAM-01`과 카메라 장치 `0`을 사용한다.
- `3f07.py`는 `CAM-02`와 카메라 장치 `1`을 사용한다.
- 기존 사무실 테스트 영상은 프로젝트 목적과 달라 삭제했다.

## CMD 실행

먼저 프로젝트 루트에서 서버를 실행한다.

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone
start_server.bat
```

새 CMD에서 실행기를 시작한다.

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone\run_video
영상 배포.bat
```

카메라가 하나라면 다음처럼 CAM-01만 실행해도 된다.

```bat
cd /d C:\Users\Ria\Desktop\capstone\re_capstone
.venv\Scripts\python.exe run_video\python\3f03.py
```

Jetson에서 Windows 서버로 보낼 때는 실행 전에 같은 공유기의 Windows IP를 지정한다.

```bat
set WINDOWS_SERVER=192.168.1.138:8000
.venv\Scripts\python.exe run_video\python\3f03.py
```
