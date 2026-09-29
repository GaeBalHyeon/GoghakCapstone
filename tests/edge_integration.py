"""Running server integration check: python tests/edge_integration.py [port]."""

import asyncio
import base64
import json
import sys
import urllib.request

import websockets


PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
HTTP = f"http://127.0.0.1:{PORT}"
WS = f"ws://127.0.0.1:{PORT}/ws/edge/CAM-01"
JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAEf/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EB//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EB//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EB//2Q=="
)


def get_json(path: str):
    with urllib.request.urlopen(HTTP + path, timeout=4) as response:
        return json.load(response)


async def main():
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
        assert events[0]["source"] == "jetson-yolo"
        assert events[0]["event_type"] == "fire"
    await asyncio.sleep(0.2)
    cameras = await asyncio.to_thread(get_json, "/api/cameras")
    camera = next(item for item in cameras if item["id"] == "CAM-01")
    assert camera["edge_online"] is False
    print("Edge WebSocket, event persistence, and disconnect checks passed.")


asyncio.run(main())

