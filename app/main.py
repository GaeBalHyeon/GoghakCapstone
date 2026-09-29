from __future__ import annotations

import asyncio
import json
import random
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
DB_PATH = DATA / "ev_fire_guard.db"

CAMERAS = [
    {"id": "CAM-01", "floor": "B1", "zone": "충전구역 A", "charger": "A-01~A-04", "x": 20, "y": 31},
    {"id": "CAM-02", "floor": "B1", "zone": "충전구역 B", "charger": "B-01~B-04", "x": 69, "y": 31},
    {"id": "CAM-03", "floor": "B1", "zone": "일반 주차구역", "charger": "-", "x": 20, "y": 71},
    {"id": "CAM-04", "floor": "B1", "zone": "출입구", "charger": "-", "x": 69, "y": 71},
]

camera_state = {
    cam["id"]: {**cam, "status": "normal", "confidence": 0.0, "fps": 8.0, "updated_at": None}
    for cam in CAMERAS
}


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


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    DATA.mkdir(exist_ok=True)
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                floor TEXT NOT NULL,
                zone TEXT NOT NULL,
                charger TEXT NOT NULL,
                event_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                resolution_note TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                simulation_enabled INTEGER NOT NULL DEFAULT 0,
                auto_event_interval INTEGER NOT NULL DEFAULT 45
            );
            INSERT OR IGNORE INTO settings(id, simulation_enabled, auto_event_interval)
            VALUES (1, 0, 45);
            """
        )


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


def get_camera(camera_id: str) -> dict:
    camera = camera_state.get(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="등록되지 않은 카메라입니다.")
    return camera


async def register_detection(req: DetectionRequest) -> dict:
    camera = get_camera(req.camera_id)
    now = utc_now()
    camera.update(status=req.event_type, confidence=req.confidence, updated_at=now)

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
        event = {**camera, "id": event_id, "event_type": req.event_type, "source": req.source, "detected_at": now}

    payload = {"kind": "detection", "camera": camera, "event": event}
    await manager.broadcast(payload)
    return payload


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


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    task = asyncio.create_task(simulator())
    yield
    task.cancel()


app = FastAPI(title="EV Fire Guard Local", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "local-simulation", "database": str(DB_PATH.name)}


@app.get("/api/cameras")
async def cameras():
    return list(camera_state.values())


@app.post("/api/detections")
async def detections(req: DetectionRequest):
    return await register_detection(req)


@app.get("/api/events")
async def events(limit: int = 100):
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM events ORDER BY detected_at DESC LIMIT ?", (min(max(limit, 1), 500),)
        ).fetchall()
    return [dict(row) for row in rows]


@app.delete("/api/events")
async def delete_events():
    with connect() as con:
        count = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        con.execute("DELETE FROM events")
    payload = {"kind": "events-cleared", "deleted": count}
    await manager.broadcast(payload)
    return payload


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
    payload = {"kind": "resolved", "event_id": event_id, "camera": camera}
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

