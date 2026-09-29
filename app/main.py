from __future__ import annotations

import asyncio
import json
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import backend_name, connect, init_db
from app.notifications import send_telegram_alert, send_telegram_system_alert, telegram_configured


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
VIDEO_DIR = ROOT / "video"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"

CAMERAS = [
    {"id": "CAM-01", "floor": "B1", "zone": "충전구역 A", "charger": "A-01~A-04", "x": 21.5, "y": 26},
    {"id": "CAM-02", "floor": "B1", "zone": "충전구역 B", "charger": "B-01~B-04", "x": 21.5, "y": 74, "local_video": "/videos/1.mp4"},
    {"id": "CAM-03", "floor": "B1", "zone": "일반 주차구역", "charger": "-", "x": 78.5, "y": 74, "local_video": "/videos/2.mp4"},
    {"id": "CAM-04", "floor": "B1", "zone": "출입구", "charger": "-", "x": 78.5, "y": 26, "local_video": "/videos/3.mp4"},
]

camera_state = {
    cam["id"]: {**cam, "status": "normal", "confidence": 0.0, "fps": 0.0, "updated_at": None, "edge_online": False}
    for cam in CAMERAS
}
charging_control_state = {
    cam["id"]: {
        "camera_id": cam["id"],
        "charger": cam["charger"],
        "zone": cam["zone"],
        "status": "available" if cam["charger"] != "-" else "not_applicable",
        "response_ms": None,
        "updated_at": None,
        "simulation": True,
    }
    for cam in CAMERAS
}
latest_frames: dict[str, bytes] = {}
frame_versions: dict[str, int] = {}
edge_connections: dict[str, int] = {}
edge_last_frame: dict[str, float] = {}
edge_seen_once: set[str] = set()
edge_offline_alerted: dict[str, bool] = {}
CAMERA_STALE_SECONDS = max(float(os.getenv("CAMERA_STALE_SECONDS", "10")), 5.0)


class DetectionRequest(BaseModel):
    camera_id: str
    event_type: Literal["fire", "smoke", "normal"]
    confidence: float = Field(default=0.92, ge=0, le=1)
    source: str = "manual"


class ResolveRequest(BaseModel):
    note: str = "관리자 확인"


class SettingsRequest(BaseModel):
    simulation_enabled: bool
    auto_event_interval: int = Field(default=45, ge=10, le=600)


class ConnectionManager:
    def __init__(self) -> None:
        self.clients: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, payload: dict) -> None:
        dead: list[WebSocket] = []
        for client in self.clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self.disconnect(client)


manager = ConnectionManager()


def utc_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def utc_now_ms() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def get_camera(camera_id: str) -> dict:
    camera = camera_state.get(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="등록되지 않은 카메라입니다.")
    return camera


async def register_detection(req: DetectionRequest) -> dict:
    camera = get_camera(req.camera_id)
    now = utc_now()
    camera.update(status=req.event_type, confidence=req.confidence, updated_at=now)
    if req.event_type == "normal":
        control = charging_control_state[camera["id"]]
        if control["status"] == "blocked":
            control.update(status="available", response_ms=None, updated_at=now)

    event = None
    if req.event_type != "normal":
        with connect() as con:
            cursor = con.execute(
                """
                INSERT INTO events(camera_id, floor, zone, charger, event_type,
                                   confidence, source, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    camera["id"], camera["floor"], camera["zone"], camera["charger"],
                    req.event_type, req.confidence, req.source, now,
                ),
            )
            event_id = cursor.lastrowid
        cutoff = {
            "cutoff_status": "not_applicable",
            "cutoff_requested_at": None,
            "cutoff_completed_at": None,
            "cutoff_response_ms": None,
        }
        if req.event_type == "fire" and camera["charger"] != "-":
            requested_at = utc_now_ms()
            started = time.perf_counter()
            await asyncio.sleep(0.18)
            response_ms = max(round((time.perf_counter() - started) * 1000), 1)
            completed_at = utc_now_ms()
            cutoff = {
                "cutoff_status": "simulated_blocked",
                "cutoff_requested_at": requested_at,
                "cutoff_completed_at": completed_at,
                "cutoff_response_ms": response_ms,
            }
            charging_control_state[camera["id"]].update(
                status="blocked",
                response_ms=response_ms,
                updated_at=completed_at,
            )
        with connect() as con:
            con.execute(
                """
                UPDATE events
                SET cutoff_status=?, cutoff_requested_at=?, cutoff_completed_at=?, cutoff_response_ms=?
                WHERE id=?
                """,
                (
                    cutoff["cutoff_status"], cutoff["cutoff_requested_at"],
                    cutoff["cutoff_completed_at"], cutoff["cutoff_response_ms"], event_id,
                ),
            )
        snapshot_path = None
        frame = latest_frames.get(camera["id"])
        if frame:
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            snapshot_path = SNAPSHOT_DIR / f"event_{event_id}_{camera['id']}.jpg"
            snapshot_path.write_bytes(frame)
            with connect() as con:
                con.execute("UPDATE events SET snapshot_path=? WHERE id=?", (snapshot_path.name, event_id))
        event = {
            "id": event_id,
            "camera_id": camera["id"],
            "floor": camera["floor"],
            "zone": camera["zone"],
            "charger": camera["charger"],
            "event_type": req.event_type,
            "confidence": req.confidence,
            "source": req.source,
            "detected_at": now,
            "resolved_at": None,
            "resolution_note": None,
            "snapshot_path": snapshot_path.name if snapshot_path else None,
            "snapshot_url": f"/api/events/{event_id}/snapshot" if snapshot_path else None,
            "notification_status": "pending" if telegram_configured() else "disabled",
            "notification_error": None,
            "notified_at": None,
            **cutoff,
        }
        with connect() as con:
            con.execute(
                "UPDATE events SET notification_status=? WHERE id=?",
                (event["notification_status"], event_id),
            )

    payload = {"kind": "detection", "camera": camera, "event": event}
    await manager.broadcast(payload)
    if event:
        asyncio.create_task(deliver_notification(dict(event), snapshot_path))
    return payload


async def deliver_notification(event: dict, snapshot_path: Path | None) -> None:
    result = await asyncio.to_thread(send_telegram_alert, event, snapshot_path)
    with connect() as con:
        con.execute(
            "UPDATE events SET notification_status=?, notification_error=?, notified_at=? WHERE id=?",
            (result.status, result.error, result.notified_at, event["id"]),
        )
    await manager.broadcast(
        {
            "kind": "notification-updated",
            "event_id": event["id"],
            "notification_status": result.status,
        }
    )


async def simulator() -> None:
    while True:
        with connect() as con:
            row = con.execute("SELECT * FROM settings WHERE id=1").fetchone()
        interval = row["auto_event_interval"]
        await asyncio.sleep(interval)
        with connect() as con:
            row = con.execute("SELECT * FROM settings WHERE id=1").fetchone()
        if not row["simulation_enabled"]:
            continue
        camera_id = random.choice(list(camera_state))
        event_type = random.choices(["normal", "smoke", "fire"], weights=[7, 2, 1])[0]
        confidence = round(random.uniform(0.78, 0.98), 2) if event_type != "normal" else 0.0
        await register_detection(
            DetectionRequest(camera_id=camera_id, event_type=event_type, confidence=confidence, source="simulator")
        )


async def deliver_camera_status_notification(camera: dict, recovered: bool) -> None:
    now = utc_now()
    if recovered:
        title = "✅ 카메라 연결 복구"
        details = [f"카메라: {camera['id']}", f"위치: {camera['floor']} {camera['zone']}", f"복구 시각: {now}"]
    else:
        title = "⚠️ 카메라 영상 끊김"
        details = [f"카메라: {camera['id']}", f"위치: {camera['floor']} {camera['zone']}", f"{CAMERA_STALE_SECONDS:.0f}초 이상 프레임이 수신되지 않았습니다.", f"감지 시각: {now}"]
    result = await asyncio.to_thread(send_telegram_system_alert, title, details)
    await manager.broadcast(
        {
            "kind": "camera-recovered" if recovered else "camera-offline",
            "camera": camera,
            "notification_status": result.status,
        }
    )


async def camera_watchdog() -> None:
    while True:
        await asyncio.sleep(2)
        now = time.monotonic()
        for camera_id in tuple(edge_seen_once):
            camera = camera_state[camera_id]
            last_frame = edge_last_frame.get(camera_id, 0)
            stale = not last_frame or now - last_frame >= CAMERA_STALE_SECONDS
            if stale and not edge_offline_alerted.get(camera_id, False):
                edge_offline_alerted[camera_id] = True
                camera.update(edge_online=False, fps=0.0)
                await manager.broadcast({"kind": "edge-status", "camera": camera})
                asyncio.create_task(deliver_camera_status_notification(dict(camera), recovered=False))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with connect() as con:
        active_cutoffs = con.execute(
            "SELECT camera_id, cutoff_response_ms, cutoff_completed_at FROM events WHERE resolved_at IS NULL AND cutoff_status=?",
            ("simulated_blocked",),
        ).fetchall()
    for event in active_cutoffs:
        control = charging_control_state.get(event["camera_id"])
        if control:
            control.update(status="blocked", response_ms=event["cutoff_response_ms"], updated_at=event["cutoff_completed_at"])
    tasks = [asyncio.create_task(simulator()), asyncio.create_task(camera_watchdog())]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="EV Fire Guard Local", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/videos", StaticFiles(directory=VIDEO_DIR), name="videos")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "edge-ready", "database": backend_name()}


@app.get("/api/cameras")
async def cameras():
    return list(camera_state.values())


@app.get("/api/charging-controls")
async def charging_controls():
    return list(charging_control_state.values())


@app.post("/api/detections")
async def detections(req: DetectionRequest):
    return await register_detection(req)


@app.get("/api/events")
async def events(limit: int = 100):
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM events ORDER BY detected_at DESC LIMIT ?", (min(max(limit, 1), 500),)
        ).fetchall()
    result = []
    for row in rows:
        event = dict(row)
        event["snapshot_url"] = f"/api/events/{event['id']}/snapshot" if event.get("snapshot_path") else None
        result.append(event)
    return result


@app.get("/api/events/{event_id}/snapshot")
async def event_snapshot(event_id: int):
    with connect() as con:
        event = con.execute("SELECT snapshot_path FROM events WHERE id=?", (event_id,)).fetchone()
    if not event or not event["snapshot_path"]:
        raise HTTPException(status_code=404, detail="저장된 스냅샷이 없습니다.")
    snapshot = (SNAPSHOT_DIR / event["snapshot_path"]).resolve()
    if SNAPSHOT_DIR.resolve() not in snapshot.parents or not snapshot.is_file():
        raise HTTPException(status_code=404, detail="스냅샷 파일이 없습니다.")
    return FileResponse(snapshot, media_type="image/jpeg", filename=snapshot.name)


@app.delete("/api/events")
async def delete_events():
    with connect() as con:
        snapshots = [row["snapshot_path"] for row in con.execute("SELECT snapshot_path FROM events WHERE snapshot_path IS NOT NULL").fetchall()]
        count = con.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
        con.execute("DELETE FROM events")
    for filename in snapshots:
        snapshot = (SNAPSHOT_DIR / filename).resolve()
        if SNAPSHOT_DIR.resolve() in snapshot.parents and snapshot.is_file():
            snapshot.unlink()
    now = utc_now()
    for camera in camera_state.values():
        camera.update(status="normal", confidence=0.0, updated_at=now)
    for control in charging_control_state.values():
        if control["status"] != "not_applicable":
            control.update(status="available", response_ms=None, updated_at=now)
    payload = {"kind": "events-cleared", "deleted": count, "cameras": list(camera_state.values())}
    await manager.broadcast(payload)
    return payload


@app.get("/api/notifications/status")
async def notification_status():
    return {"telegram_configured": telegram_configured()}


@app.put("/api/events/{event_id}/resolve")
async def resolve(event_id: int, req: ResolveRequest):
    resolved_at = utc_now()
    with connect() as con:
        event = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="이벤트가 없습니다.")
        con.execute(
            "UPDATE events SET resolved_at=?, resolution_note=? WHERE id=?",
            (resolved_at, req.note, event_id),
        )
    camera = get_camera(event["camera_id"])
    camera.update(status="normal", confidence=0.0, updated_at=resolved_at)
    control = charging_control_state[camera["id"]]
    if control["status"] == "blocked":
        control.update(status="available", response_ms=None, updated_at=resolved_at)
    payload = {"kind": "resolved", "event_id": event_id, "camera": camera, "charging_control": control}
    await manager.broadcast(payload)
    return payload


@app.get("/api/settings")
async def settings():
    with connect() as con:
        row = con.execute("SELECT * FROM settings WHERE id=1").fetchone()
    return {"simulation_enabled": bool(row["simulation_enabled"]), "auto_event_interval": row["auto_event_interval"]}


@app.put("/api/settings")
async def update_settings(req: SettingsRequest):
    with connect() as con:
        con.execute(
            "UPDATE settings SET simulation_enabled=?, auto_event_interval=? WHERE id=1",
            (int(req.simulation_enabled), req.auto_event_interval),
        )
    return req.model_dump()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"kind": "connected", "message": "실시간 관제 연결됨"}, ensure_ascii=False))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/edge/{camera_id}")
async def edge_websocket(websocket: WebSocket, camera_id: str):
    camera = camera_state.get(camera_id)
    if not camera:
        await websocket.close(code=4404, reason="Unknown camera")
        return
    expected_token = os.getenv("EDGE_TOKEN", "")
    authorization = websocket.headers.get("authorization", "")
    header_token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    supplied_token = header_token or websocket.query_params.get("token", "")
    if expected_token and supplied_token != expected_token:
        await websocket.close(code=4401, reason="Invalid edge token")
        return

    await websocket.accept()
    edge_connections[camera_id] = edge_connections.get(camera_id, 0) + 1
    edge_seen_once.add(camera_id)
    edge_last_frame[camera_id] = time.monotonic()
    recovered = edge_offline_alerted.pop(camera_id, False)
    camera["edge_online"] = True
    camera["updated_at"] = utc_now()
    await manager.broadcast({"kind": "edge-status", "camera": camera})
    if recovered:
        asyncio.create_task(deliver_camera_status_notification(dict(camera), recovered=True))
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                latest_frames[camera_id] = message["bytes"]
                frame_versions[camera_id] = frame_versions.get(camera_id, 0) + 1
                edge_last_frame[camera_id] = time.monotonic()
                camera["updated_at"] = utc_now()
                continue
            if message.get("text"):
                data = json.loads(message["text"])
                camera["fps"] = round(float(data.get("fps", camera["fps"])), 1)
                if data.get("kind") == "detection":
                    await register_detection(
                        DetectionRequest(
                            camera_id=camera_id,
                            event_type=data["event_type"],
                            confidence=float(data.get("confidence", 0)),
                            source="jetson-yolo",
                        )
                    )
    except (WebSocketDisconnect, json.JSONDecodeError, KeyError, ValueError):
        pass
    finally:
        edge_connections[camera_id] = max(edge_connections.get(camera_id, 1) - 1, 0)
        camera["edge_online"] = edge_connections[camera_id] > 0
        if not camera["edge_online"]:
            camera["fps"] = 0.0
        await manager.broadcast({"kind": "edge-status", "camera": camera})


@app.get("/api/video_feed/{camera_id}")
async def video_feed(camera_id: str):
    get_camera(camera_id)

    async def stream():
        version = -1
        while True:
            current = frame_versions.get(camera_id, 0)
            frame = latest_frames.get(camera_id)
            if frame is not None and current != version:
                version = current
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.04)

    return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame")

