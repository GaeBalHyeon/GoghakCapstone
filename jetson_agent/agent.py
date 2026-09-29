from __future__ import annotations

import json
import os
import threading
import time
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
CONFIRM_SECONDS = float(os.getenv("CONFIRM_SECONDS", "3.0"))
MISS_TOLERANCE_SECONDS = float(os.getenv("MISS_TOLERANCE_SECONDS", "0.6"))
CLEAR_SECONDS = float(os.getenv("CLEAR_SECONDS", "2.0"))


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
    url = f"ws://{SERVER}/ws/edge/{quote(CAMERA_ID)}"
    ws = websocket.create_connection(
        url,
        timeout=10,
        enable_multithread=True,
        header=[f"Authorization: Bearer {TOKEN}"],
    )
    ws.settimeout(None)
    threading.Thread(target=drain_incoming, args=(ws,), daemon=True).start()
    return ws


def main():
    model = YOLO(MODEL_PATH)
    capture = cv2.VideoCapture(camera_source())
    if not capture.isOpened():
        raise RuntimeError(f"카메라를 열 수 없습니다: {camera_source()}")

    active = {"fire": False, "smoke": False}
    candidate_since = {"fire": None, "smoke": None}
    last_seen = {"fire": None, "smoke": None}
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

            detection_now = time.perf_counter()
            cleared_detection = False
            for kind in ("fire", "smoke"):
                if seen[kind] > 0:
                    last_seen[kind] = detection_now
                    if candidate_since[kind] is None:
                        candidate_since[kind] = detection_now
                    if not active[kind] and detection_now - candidate_since[kind] >= CONFIRM_SECONDS:
                        active[kind] = True
                        pending_events.append({
                            "kind": "detection", "event_type": kind,
                            "confidence": seen[kind], "fps": measured_fps,
                        })
                elif active[kind]:
                    if last_seen[kind] is None or detection_now - last_seen[kind] >= CLEAR_SECONDS:
                        active[kind] = False
                        candidate_since[kind] = None
                        last_seen[kind] = None
                        cleared_detection = True
                elif candidate_since[kind] is not None:
                    if last_seen[kind] is None or detection_now - last_seen[kind] >= MISS_TOLERANCE_SECONDS:
                        candidate_since[kind] = None
                        last_seen[kind] = None
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
            verifying = [
                (kind, min(detection_now - started, CONFIRM_SECONDS))
                for kind, started in candidate_since.items()
                if started is not None and not active[kind]
            ]
            if verifying:
                kind, duration = max(verifying, key=lambda item: item[1])
                cv2.putText(
                    annotated,
                    f"VERIFY {kind.upper()}  {duration:.1f}/{CONFIRM_SECONDS:.1f}s",
                    (16, 56), cv2.FONT_HERSHEY_SIMPLEX, .62, (0, 190, 255), 2,
                )
            encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if not encoded:
                continue

            try:
                if ws is None or not ws.connected:
                    ws = connect_websocket()
                ws.send_binary(jpeg.tobytes())
                while pending_events:
                    ws.send(json.dumps(pending_events[0]))
                    pending_events.pop(0)
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

