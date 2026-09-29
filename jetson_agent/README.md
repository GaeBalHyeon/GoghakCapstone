# Jetson YOLO 에이전트

Jetson에 연결된 카메라 영상을 YOLO로 분석한 뒤, 박스가 그려진 JPEG 프레임과 확정된 화재·연기 이벤트를 Windows 서버로 전송합니다.

## 준비

1. 이 폴더를 Jetson으로 복사합니다.
2. 학습 모델 `best.pt`를 이 폴더에 둡니다.
3. `.env.example`을 `.env`로 복사합니다.
4. `WINDOWS_SERVER`에 Windows PC의 내부 IP와 포트 8000을 입력합니다.
5. Windows 프로젝트의 `.env`와 같은 `EDGE_TOKEN`을 입력합니다.

```bash
python3 -m pip install -r requirements.txt
python3 agent.py
```

USB 카메라는 `CAMERA_SOURCE=0`, RTSP 카메라는 `CAMERA_SOURCE=rtsp://...` 형식으로 설정합니다. 모델 클래스 이름에는 `fire` 또는 `smoke`가 포함되어야 합니다.

화재·연기는 기본적으로 최근 20프레임 중 10프레임 이상 감지됐을 때 한 번의 확정 이벤트로 전송합니다.

