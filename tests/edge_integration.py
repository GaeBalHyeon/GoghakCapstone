"""Running server integration check: python tests/edge_integration.py [port]."""

import asyncio
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

import websockets
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import connect


PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
HTTP = f"http://127.0.0.1:{PORT}"
load_dotenv(ROOT / ".env")
TOKEN = os.getenv("EDGE_TOKEN", "")
WS = f"ws://127.0.0.1:{PORT}/ws/edge/CAM-01?token={quote(TOKEN)}"
JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAEf/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EB//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EB//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EB//2Q=="
)


def get_json(path: str):
    with urllib.request.urlopen(HTTP + path, timeout=4) as response:
        return json.load(response)


def get_bytes(path: str):
    with urllib.request.urlopen(HTTP + path, timeout=4) as response:
        return response.status, response.headers.get_content_type(), response.read()


def read_video_range(path: str):
    request = urllib.request.Request(HTTP + path, headers={"Range": "bytes=0-1023"})
    with urllib.request.urlopen(request, timeout=4) as response:
        return response.status, response.headers.get("Content-Range"), response.read()


def delete_test_event(event_id: int):
    with connect() as con:
        event = con.execute("SELECT snapshot_path FROM events WHERE id=?", (event_id,)).fetchone()
        con.execute("DELETE FROM events WHERE id=?", (event_id,))
    if event and event["snapshot_path"]:
        snapshot = ROOT / "data" / "snapshots" / event["snapshot_path"]
        snapshot.unlink(missing_ok=True)


async def main():
    event_id = None
    try:
        cameras = await asyncio.to_thread(get_json, "/api/cameras")
        expected_local = {"CAM-02": "/videos/1.mp4", "CAM-03": "/videos/2.mp4", "CAM-04": "/videos/3.mp4"}
        assert {camera["id"]: camera.get("local_video") for camera in cameras if camera["id"] in expected_local} == expected_local
        assert next(camera for camera in cameras if camera["id"] == "CAM-01").get("local_video") is None

        for video_path in expected_local.values():
            status, content_range, content = await asyncio.to_thread(read_video_range, video_path)
            assert status == 206
            assert content_range and content_range.startswith("bytes 0-1023/")
            assert len(content) == 1024

        async with websockets.connect(WS) as socket:
            await socket.send(JPEG)
            await socket.send(json.dumps({"kind": "heartbeat", "fps": 7.8}))
            await socket.send(json.dumps({"kind": "detection", "event_type": "fire", "confidence": 0.93, "fps": 7.8}))
            await asyncio.sleep(0.2)
            cameras = await asyncio.to_thread(get_json, "/api/cameras")
            camera = next(item for item in cameras if item["id"] == "CAM-01")
            assert camera["edge_online"] is True
            assert camera["fps"] == 7.8
            events = await asyncio.to_thread(get_json, "/api/events")
            test_event = next(event for event in events if event["source"] == "jetson-yolo" and event["event_type"] == "fire")
            event_id = test_event["id"]
            assert test_event["snapshot_url"]
            status, content_type, snapshot = await asyncio.to_thread(get_bytes, test_event["snapshot_url"])
            assert status == 200 and content_type == "image/jpeg" and snapshot == JPEG
            assert test_event["notification_status"] in {"disabled", "pending", "sent"}
            await socket.send(json.dumps({"kind": "detection", "event_type": "normal", "confidence": 0.0, "fps": 7.8}))
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.2)
        cameras = await asyncio.to_thread(get_json, "/api/cameras")
        camera = next(item for item in cameras if item["id"] == "CAM-01")
        assert camera["edge_online"] is False
        assert camera["status"] == "normal"
        print("Live feed, snapshot persistence, local videos, notification state, and disconnect checks passed.")
    finally:
        if event_id is not None:
            delete_test_event(event_id)


asyncio.run(main())

