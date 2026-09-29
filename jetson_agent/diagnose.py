from __future__ import annotations

import glob
import json
import os
import platform
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def result(label: str, ok: bool, detail: str):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    return ok


def main():
    checks = []
    print("EV Fire Guard Jetson diagnostics")
    print("=" * 48)
    print(f"OS: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Machine: {platform.machine()}")

    try:
        import torch
        cuda = torch.cuda.is_available()
        name = torch.cuda.get_device_name(0) if cuda else "CUDA unavailable"
        checks.append(result("PyTorch CUDA", cuda, f"torch={torch.__version__}, device={name}"))
    except Exception as error:
        checks.append(result("PyTorch CUDA", False, repr(error)))

    try:
        import cv2
        checks.append(result("OpenCV import", True, cv2.__version__))
        devices = glob.glob("/dev/video*")
        checks.append(result("Camera devices", bool(devices), ", ".join(devices) if devices else "none"))
        source_raw = os.getenv("CAMERA_SOURCE", "0")
        source = int(source_raw) if source_raw.isdigit() else source_raw
        capture = cv2.VideoCapture(source)
        opened = capture.isOpened()
        ok, frame = capture.read() if opened else (False, None)
        detail = f"source={source_raw}" + (f", frame={frame.shape[1]}x{frame.shape[0]}" if ok else "")
        capture.release()
        checks.append(result("Camera capture", opened and ok, detail))
    except Exception as error:
        checks.append(result("Camera capture", False, repr(error)))

    model_path = ROOT / os.getenv("MODEL_PATH", "best.pt")
    checks.append(result("Model file", model_path.is_file(), str(model_path)))
    if model_path.is_file():
        try:
            from ultralytics import YOLO
            model = YOLO(str(model_path))
            names = model.names
            values = {str(value).lower() for value in names.values()}
            checks.append(result("Model classes", {"fire", "smoke"}.issubset(values), json.dumps(names, ensure_ascii=False)))
        except Exception as error:
            checks.append(result("Model load", False, repr(error)))

    server = os.getenv("WINDOWS_SERVER", "127.0.0.1:8000")
    try:
        with urllib.request.urlopen(f"http://{server}/api/health", timeout=4) as response:
            data = json.load(response)
        checks.append(result("Windows server", data.get("status") == "ok", f"http://{server}, {data}"))
    except Exception as error:
        checks.append(result("Windows server", False, f"http://{server}: {error}"))

    token = os.getenv("EDGE_TOKEN", "")
    camera_id = os.getenv("CAMERA_ID", "CAM-01")
    if not token or token == "change-this-edge-token":
        checks.append(result("Edge token", False, "Set EDGE_TOKEN to the value from the Windows .env file"))
    else:
        try:
            import websocket

            ws_url = f"ws://{server}/ws/edge/{quote(camera_id)}"
            ws = websocket.create_connection(
                ws_url,
                timeout=4,
                header=[f"Authorization: Bearer {token}"],
            )
            ws.close()
            checks.append(result("Edge WebSocket", True, ws_url))
        except Exception as error:
            checks.append(result("Edge WebSocket", False, repr(error)))

    print("=" * 48)
    print(f"Result: {sum(checks)}/{len(checks)} checks passed")
    raise SystemExit(0 if all(checks) else 1)


if __name__ == "__main__":
    main()

