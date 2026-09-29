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

# Vehicle detection uses a pretrained COCO model, so no extra training is needed.
VEHICLE_DETECTION = os.getenv("VEHICLE_DETECTION", "1").strip().lower() in ("1", "true", "yes", "on")
VEHICLE_MODEL_PATH = os.getenv("VEHICLE_MODEL_PATH", "yolo11n.pt")
VEHICLE_CONFIDENCE = float(os.getenv("VEHICLE_CONFIDENCE", "0.4"))
VEHICLE_EVERY_N_FRAMES = max(int(os.getenv("VEHICLE_EVERY_N_FRAMES", "3")), 1)
VEHICLE_REPORT_SECONDS = 2.0
VEHICLE_CLASSES = {"car": "승용차", "truck": "트럭", "bus": "버스", "motorcycle": "오토바이"}
VEHICLE_COLOR = (255, 170, 0)  # BGR: blue boxes, distinct from fire/smoke boxes


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


def load_vehicle_model():
    if not VEHICLE_DETECTION:
        return None
    try:
        vehicle_model = YOLO(VEHICLE_MODEL_PATH)
    except Exception as error:
        # Fire detection must keep working even if the vehicle model is unavailable.
        print(f"차량 감지 모델을 불러오지 못해 차량 감지를 끕니다: {error}")
        return None
    class_ids = [cid for cid, name in vehicle_model.names.items() if str(name) in VEHICLE_CLASSES]
    if not class_ids:
        print("차량 감지 모델에 car/truck/bus/motorcycle 클래스가 없어 차량 감지를 끕니다.")
        return None
    print(f"차량 감지 사용: {VEHICLE_MODEL_PATH}, {VEHICLE_EVERY_N_FRAMES}프레임마다 추론")
    return vehicle_model, class_ids


def detect_vehicles(vehicle, frame):
    vehicle_model, class_ids = vehicle
    result = vehicle_model.predict(frame, conf=VEHICLE_CONFIDENCE, classes=class_ids, verbose=False)[0]
    boxes = []
    for box in result.boxes:
        name = str(vehicle_model.names[int(box.cls[0])])
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        boxes.append((name, float(box.conf[0]), (x1, y1, x2, y2)))
    return boxes


def draw_vehicles(image, boxes):
    for name, confidence, (x1, y1, x2, y2) in boxes:
        cv2.rectangle(image, (x1, y1), (x2, y2), VEHICLE_COLOR, 2)
        cv2.putText(image, f"{name} {confidence:.2f}", (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, .5, VEHICLE_COLOR, 2)
    label = f"VEHICLE {len(boxes)}"
    (width, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .65, 2)
    cv2.putText(image, label, (image.shape[1] - width - 16, 28), cv2.FONT_HERSHEY_SIMPLEX, .65, VEHICLE_COLOR, 2)


def main():
    model = YOLO(MODEL_PATH)
    vehicle = load_vehicle_model()
    vehicle_boxes = []
    recent_vehicle_counts = []
    reported_vehicle_count = None
    last_vehicle_report = 0.0
    frame_index = 0
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

            frame_index += 1
            if vehicle and frame_index % VEHICLE_EVERY_N_FRAMES == 0:
                vehicle_boxes = detect_vehicles(vehicle, frame)
                # Use the max of the last few inferences so one missed frame does not flicker the count.
                recent_vehicle_counts = (recent_vehicle_counts + [len(vehicle_boxes)])[-3:]
                vehicle_count = max(recent_vehicle_counts)
                vehicle_now = time.perf_counter()
                if vehicle_count != reported_vehicle_count or vehicle_now - last_vehicle_report >= VEHICLE_REPORT_SECONDS:
                    types = {}
                    for name, _, _ in vehicle_boxes:
                        types[name] = types.get(name, 0) + 1
                    # Only the latest vehicle status matters, so drop older unsent ones.
                    pending_events[:] = [item for item in pending_events if item.get("kind") != "vehicle"]
                    pending_events.append({"kind": "vehicle", "count": vehicle_count, "types": types, "fps": measured_fps})
                    reported_vehicle_count = vehicle_count
                    last_vehicle_report = vehicle_now

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
            if vehicle:
                draw_vehicles(annotated, vehicle_boxes)
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

