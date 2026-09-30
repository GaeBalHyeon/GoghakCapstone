# Jetson 성능과 카메라 확장 분석

측정일: 2026-09-30  
장비: NVIDIA Jetson Orin Nano Super 8GB  
전력 모드: `MAXN_SUPER`

## 측정 당시 실행 구성

- USB 카메라 1대, CAM-01
- 화재 학습 모델 `best.pt`: 매 프레임 추론
- 연기 감지: OFF (`SMOKE_DETECTION=0`)
- 차량 모델 `yolo11n.pt`: 3프레임마다 추론
- JPEG 생성과 Windows WebSocket 전송
- Windows 홈페이지 수신 FPS: 약 24.7~25.8 FPS

## 12초 실측 결과

| 항목 | 결과 |
|---|---:|
| GPU 사용률 | 평균 약 78%, 범위 43~98% |
| AI 에이전트 CPU | 약 95%, CPU 코어 1개 수준 지속 점유 |
| 시스템 RAM | 3.37GB / 7.62GB 사용 |
| 사용 가능 RAM | 약 4.0GB |
| 에이전트 RSS | 약 1.59GB |
| Swap | 0GB 사용 |
| GPU 최고 온도 | 약 62.5°C |
| 전체 입력 전력 | 평균 약 13.7W |
| 시스템 Load Average | 약 1.6 |

온도와 메모리는 여유가 있지만 GPU가 주 병목이다. GPU가 순간 98%까지 도달하므로 현재 파이프라인을 그대로 복제해 카메라를 한 대 더 붙이면 실시간성이 크게 떨어질 가능성이 높다.

## 카메라 추가 판단

### 현재 코드와 품질 그대로

- 안정 권장: AI 카메라 1대
- 추가 가능: 저장 영상이나 AI 없는 단순 스트림 1~3대
- 비권장: 화재+차량 YOLO를 동일하게 수행하는 두 번째 실시간 카메라

현재 평균 GPU 사용률을 단순 선형 환산하면 같은 파이프라인 두 개는 약 156%의 GPU 수요가 필요하다. 실제로는 메모리 복사, JPEG 인코딩과 카메라 I/O 경합도 생기므로 2대가 안정적으로 25 FPS를 유지할 수 없다.

### 2대의 AI 카메라를 목표로 할 때

다음 조건을 적용하면 현실적인 검증 대상이 된다.

1. 차량 탐지를 끄거나 중앙 카메라 한 대에서만 실행
2. 각 카메라의 AI 추론을 8~12 FPS로 제한하고 화면 전송은 최신 프레임 사용
3. 화재 모델을 TensorRT FP16 엔진으로 변환
4. 카메라별 모델을 각각 로드하지 않고 한 프로세스에서 모델 하나를 공유
5. 입력 크기를 필요한 수준으로 축소

목표는 2대 × 10~15 FPS가 적절하다. 실제 수치는 TensorRT 변환 후 반드시 다시 측정해야 한다.

### 3~4대의 AI 카메라를 목표로 할 때

- TensorRT FP16/INT8 최적화
- 프레임 배치 추론
- 카메라별 5~8 FPS 분석
- JPEG 대신 하드웨어 H.264 스트림 또는 저해상도 미리보기
- 차량 탐지는 낮은 주기 또는 별도 장비로 분리

위 구조라면 3~4대를 시험할 가치는 있지만, 현재 PyTorch 코드 상태에서 4대 실시간 분석이 가능하다고 발표하면 안 된다. 실측 검증 전에는 목표 사양으로만 표기한다.

## 일반 PC와의 성능 비교

Jetson Orin Nano Super의 공식 사양은 67 INT8 TOPS, 1024 CUDA 코어, 32 Tensor 코어, 6코어 Arm Cortex-A78AE CPU, 8GB LPDDR5와 102GB/s 메모리 대역폭이다.

- 일반 작업 CPU 성능: 최신 데스크톱 Core i5/Ryzen 5보다 상당히 낮은 보급형 미니 PC 수준
- CPU만 사용하는 PC AI 추론: Jetson GPU가 전력 효율과 지속 추론에서 유리
- NVIDIA RTX가 장착된 데스크톱: RTX 3050/3060급 이상 PC가 보통 더 높은 절대 추론 성능과 확장성을 제공
- 전력 효율과 크기: 약 14W 실측으로 카메라 옆에서 독립 동작하는 Jetson이 훨씬 유리

67 TOPS는 INT8 및 희소성 조건의 AI 지표이므로 PC CPU 점수나 데스크톱 GPU의 FP32 수치와 직접 같은 값으로 비교하면 안 된다. 이 장비는 데스크톱 대체품이 아니라 저전력 엣지 AI 전용 컴퓨터로 보는 것이 정확하다.

## 결론

현재 구성은 카메라 1대에서 약 25 FPS로 안정적이지만 GPU 여유가 약 20%뿐이다. 시연 안정성을 우선하면 현재 1대를 유지한다. AI 카메라 2대를 사용하려면 차량 탐지 주기 축소 또는 비활성화와 TensorRT 최적화를 먼저 수행하는 것이 좋다.

## 공식 사양 출처

- NVIDIA Jetson Orin Nano Super Developer Kit: https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/
- NVIDIA Jetson 교육용 개발 키트 사양표: https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson/back-to-school/
