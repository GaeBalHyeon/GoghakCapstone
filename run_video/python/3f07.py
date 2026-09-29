"""CAM-02 camera launcher for the local fire/smoke detection system."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "jetson_agent"

os.environ.setdefault("WINDOWS_SERVER", "127.0.0.1:8000")
os.environ.setdefault("CAMERA_ID", "CAM-02")
os.environ.setdefault("CAMERA_SOURCE", "1")
os.environ.setdefault("MODEL_PATH", str(Path(__file__).with_name("best.pt")))
os.environ.setdefault("CONFIDENCE", "0.40")
os.environ.setdefault("TARGET_FPS", "8")
os.environ.setdefault("WINDOW_SIZE", "20")
os.environ.setdefault("MIN_DETECTIONS", "10")

sys.path.insert(0, str(AGENT_DIR))
from agent import main  # noqa: E402


if __name__ == "__main__":
    main()
