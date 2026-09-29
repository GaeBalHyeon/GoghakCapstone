# YOLO 모델 사전 평가

## 평가 환경

- 모델: `jetson_agent/best.pt`
- 클래스: `{0: fire, 1: smoke}`
- Ultralytics: `8.3.0`
- PyTorch: `2.5.1+cpu`
- 장치: Windows CPU
- 입력: `video` 폴더의 MP4 3개
- 표본 방식: 영상마다 1초 간격 프레임
- 탐지 신뢰도 기준: `0.25`

처음 설치된 PyTorch 빌드는 `c10.dll` 초기화에 실패했습니다. 공식 PyTorch CPU 인덱스의 `torch 2.5.1+cpu`, `torchvision 0.20.1+cpu`로 교체한 뒤 모델 로드와 추론이 정상 동작했습니다.

## 결과

| 영상 | 표본 프레임 | 화재 박스 | 연기 박스 | 화재 최대 신뢰도 | 연기 최대 신뢰도 |
|---|---:|---:|---:|---:|---:|
| `1.mp4` | 23 | 4 | 2 | 0.7600 | 0.5182 |
| `2.mp4` | 43 | 9 | 1 | 0.7405 | 0.6498 |
| `3.mp4` | 23 | 10 | 0 | 0.8171 | 0 |

주요 구간:

- `1.mp4`: 시작부터 약 2초까지 화재와 연기 검출
- `2.mp4`: 시작 시 연기, 약 11~20초와 36초 부근 화재 검출
- `3.mp4`: 약 13~22초 동안 연속 화재 검출

## 종단 간 전송 검증

`video/3.mp4`를 Jetson 카메라 입력처럼 사용해 다음 전체 경로를 검증했습니다.

```text
영상 파일 → YOLO 추론 → 박스 표시 JPEG → Edge WebSocket
→ Windows FastAPI → MJPEG 영상 → 홈페이지용 URL
→ 화재 이벤트 → 로컬 DB
```

확인 결과:

- Edge 연결 상태: `True`
- 측정 추론 FPS: `13.6`
- 카메라 상태: `fire`
- 저장 이벤트: `fire`, `source=jetson-yolo`
- 이벤트 신뢰도: 약 `0.7499`
- MJPEG Content-Type 및 JPEG 헤더 확인
- 에이전트 종료 후 Edge 상태가 `False`로 변경

이 결과는 Windows CPU와 영상 파일을 사용한 기능 검증입니다. Jetson 카메라와 CUDA 성능 검증은 `jetson_agent/diagnose.py`로 별도 수행해야 합니다.

## 재실행

Windows 모델 평가용 패키지가 설치된 환경에서:

```bat
.venv\Scripts\python.exe tools\evaluate_videos.py
```

