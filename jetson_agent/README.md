# Jetson YOLO 에이전트

Jetson에 연결된 카메라 영상을 YOLO로 분석한 뒤, 박스가 그려진 JPEG 프레임과 확정된 화재·연기 이벤트를 Windows 서버로 전송합니다.

## 준비

1. 이 폴더를 Jetson으로 복사합니다.
2. 저장소에 포함된 `best.pt`를 사용합니다. 모델 클래스는 `fire`, `smoke`로 확인했습니다.
3. `.env.example`을 `.env`로 복사합니다.
4. `WINDOWS_SERVER`에 Windows PC의 내부 IP와 포트 8000을 입력합니다.
5. Windows 프로젝트의 `.env`와 같은 `EDGE_TOKEN`을 입력합니다.

JetPack의 CUDA PyTorch와 OpenCV를 보존하는 설치 스크립트를 사용합니다.

```bash
chmod +x setup_jetson.sh
./setup_jetson.sh
nano .env
python3 diagnose.py
python3 agent.py
```

`diagnose.py`에서 CUDA, 카메라, 모델 클래스와 Windows 서버 연결이 모두 PASS인지 확인한 뒤 에이전트를 실행합니다.

USB 카메라는 `CAMERA_SOURCE=0`, RTSP 카메라는 `CAMERA_SOURCE=rtsp://...` 형식으로 설정합니다. 모델 클래스 이름에는 `fire` 또는 `smoke`가 포함되어야 합니다.

영상 파일로 먼저 시험하려면 `CAMERA_SOURCE=../video/1.mp4`처럼 설정할 수 있으며 영상 끝에 도달하면 처음부터 반복합니다.

화재·연기는 기본적으로 3초 동안 지속해서 감지됐을 때 한 번의 확정 이벤트로 전송합니다. 0.6초 이내의 짧은 검출 누락은 허용하고, 2초 동안 사라지면 정상으로 복귀합니다. 이 방식은 카메라 FPS가 달라져도 확인 시간이 일정하며 별도의 AI 추론을 추가하지 않습니다.

연기 감지를 사용하지 않으려면 `.env`에 `SMOKE_DETECTION=0`을 설정합니다. 이 경우 화재 클래스만 YOLO 결과로 사용하며 연기 박스와 연기 이벤트는 생성하지 않습니다.

## 재부팅 후 자동 실행

Jetson에서 다음 명령을 한 번 실행하면 사용자 crontab에 자동 실행 항목이 등록됩니다. 부팅 20초 후 에이전트를 시작하며, 에이전트가 비정상 종료되면 5초 뒤 다시 실행합니다.

```bash
cd ~/evguard/jetson_agent
chmod +x install_autostart.sh
./install_autostart.sh
```

등록 확인은 `crontab -l`, 실행 로그 확인은 `tail -f ~/evguard/agent.log`를 사용합니다.

