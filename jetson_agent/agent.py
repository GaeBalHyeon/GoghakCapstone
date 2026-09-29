from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import quote

import cv2
import websocket
from dotenv import load_dotenv
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

SERVER = os.getenv("WINDOWS_SERVER", "127.0.0.1:8000")
TOKEN = os.getenv("EDGE_TOKEN", "")
CAMERA_ID = os.getenv("CAMERA_ID", "CAM-01")
MODEL_PATH = os.getenv("MODEL_PATH", "best.pt")
CONFIDENCE = float(os.getenv("CONFIDENCE", "0.45"))
TARGET_FPS = float(os.getenv("TARGET_FPS", "8"))
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "20"))
MIN_DETECTIONS = int(os.getenv("MIN_DETECTIONS", "10"))


def camera_source():
    raw = os.getenv("CAMERA_SOURCE", "0")
    return int(raw) if raw.isdigit() else raw


def class_kind(name: str) -> str | None:
    normalized = name.lower().strip()
    if any(word in normalized for word in ("fire", "flame", "화재", "불꽃")):
        return "fire"
    if any(word in normalized for word in ("smoke", "연기")):
        return "smoke"
    return None


def drain_incoming(ws):
    # The server sends WebSocket pings. websocket-client only answers them while
    # reading, so keep a reader running or the server drops the connection.
    try:
        while ws.connected:
            ws.recv()
    except Exception:
        pass


def connect_websocket():
    url = f"ws://{SERVER}/ws/edge/{quote(CAMERA_ID)}?token={quote(TOKEN)}"
    ws = websocket.create_connection(url, timeout=10, enable_multithread=True)
    ws.settimeout(None)
    threading.Thread(target=drain_incoming, args=(ws,), daemon=True).start()
    return ws


def main():
    model = YOLO(MODEL_PATH)
    capture = cv2.VideoCapture(camera_source())
    if not capture.isOpened():
        raise RuntimeError(f"카메라를 열 수 없습니다: {camera_source()}")

    histories = {"fire": deque(maxlen=WINDOW_SIZE), "smoke": deque(maxlen=WINDOW_SIZE)}
    active = {"fire": False, "smoke": False}
    pending_events = []
    ws = None
    frame_interval = 1.0 / max(TARGET_FPS, 1)
    last_sent = 0.0
    fps_started = time.perf_counter()
    fps_frames = 0
    measured_fps = 0.0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                if isinstance(camera_source(), str) and Path(camera_source()).is_file():
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.2)
                continue

            result = model.predict(frame, conf=CONFIDENCE, verbose=False)[0]
            seen = {"fire": 0.0, "smoke": 0.0}
            for box in result.boxes:
                kind = class_kind(str(model.names[int(box.cls[0])]))
                if kind:
                    seen[kind] = max(seen[kind], float(box.conf[0]))

            fps_frames += 1
            elapsed = time.perf_counter() - fps_started
            if elapsed >= 1:
                measured_fps = fps_frames / elapsed
                fps_frames = 0
                fps_started = time.perf_counter()

            cleared_detection = False
            for kind in ("fire", "smoke"):
                histories[kind].append(seen[kind] > 0)
                confirmed = len(histories[kind]) == WINDOW_SIZE and sum(histories[kind]) >= MIN_DETECTIONS
                if confirmed and not active[kind]:
                    active[kind] = True
                    pending_events.append({
                        "kind": "detection", "event_type": kind,
                        "confidence": seen[kind], "fps": measured_fps,
                    })
                elif not confirmed and active[kind] and sum(histories[kind]) == 0:
                    active[kind] = False
                    cleared_detection = True
            if cleared_detection and not any(active.values()):
                pending_events.append({
                    "kind": "detection", "event_type": "normal",
                    "confidence": 0.0, "fps": measured_fps,
                })

            now = time.perf_counter()
            if now - last_sent < frame_interval:
                continue
            last_sent = now
            annotated = result.plot()
            cv2.putText(annotated, f"{CAMERA_ID}  {measured_fps:.1f} FPS", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2)
            encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if not encoded:
                continue

            try:
                if ws is None or not ws.connected:
                    ws = connect_websocket()
                while pending_events:
                    ws.send(json.dumps(pending_events[0]))
                    pending_events.pop(0)
                ws.send_binary(jpeg.tobytes())
                if int(now) % 5 == 0:
                    ws.send(json.dumps({"kind": "heartbeat", "fps": measured_fps}))
            except Exception as error:
                print(f"Windows 서버 연결 대기: {error}")
                if ws:
                    ws.close()
                ws = None
                time.sleep(2)
    finally:
        capture.release()
        if ws:
            ws.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nJetson agent stopped.")

