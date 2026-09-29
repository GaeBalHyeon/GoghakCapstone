#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 - <<'PY'
import cv2
import torch
print("Existing Jetson packages:")
print("  OpenCV:", cv2.__version__)
print("  PyTorch:", torch.__version__)
print("  CUDA:", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit("CUDA-enabled PyTorch is required. Install the NVIDIA JetPack-compatible wheel first.")
PY

# Preserve NVIDIA's CUDA PyTorch and JetPack OpenCV.
python3 -m pip install --no-deps ultralytics==8.3.0
python3 -m pip install websocket-client==1.8.0 python-dotenv==1.0.1 pyyaml requests tqdm psutil py-cpuinfo

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Edit WINDOWS_SERVER and EDGE_TOKEN before running."
fi

echo "Jetson agent dependencies are ready."
echo "Next: python3 diagnose.py"

