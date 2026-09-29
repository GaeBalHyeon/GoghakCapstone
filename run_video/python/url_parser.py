"""Legacy-name compatibility utility: check the local server and cameras."""

import json
import os
from urllib.request import urlopen


SERVER = os.getenv("WINDOWS_SERVER", "127.0.0.1:8000")
BASE_URL = f"http://{SERVER}"


def get_json(path: str):
    with urlopen(f"{BASE_URL}{path}", timeout=3) as response:
        return json.load(response)


if __name__ == "__main__":
    print("AWS/Cloudflare tunnel: disabled")
    print(f"Local server: {BASE_URL}")
    try:
        health = get_json("/api/health")
        cameras = get_json("/api/cameras")
        print(f"Server status: {health.get('status', 'unknown')}")
        for camera in cameras:
            print(
                f"{camera['id']}: online={camera.get('edge_online', False)}, "
                f"fps={camera.get('fps', 0)}"
            )
    except Exception as exc:
        raise SystemExit(f"Local server connection failed: {exc}") from exc
