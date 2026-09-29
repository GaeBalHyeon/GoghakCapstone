from __future__ import annotations

import os
import socket
import subprocess
import sys
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values


def report(label: str, state: str, detail: str):
    print(f"[{state}] {label}: {detail}")
    return state != "FAIL"


def main():
    checks = []
    print("EV Fire Guard Windows diagnostics")
    print("=" * 52)
    print(f"Python: {sys.version.split()[0]}")

    env_path = ROOT / ".env"
    env = dotenv_values(env_path) if env_path.exists() else {}
    checks.append(report("Environment file", "PASS" if env else "FAIL", str(env_path)))
    required = ["DATABASE_BACKEND", "MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "EDGE_TOKEN"]
    missing = [key for key in required if not env.get(key)]
    checks.append(report("Environment values", "PASS" if not missing else "FAIL", "complete" if not missing else "missing " + ", ".join(missing)))

    service = subprocess.run(["sc.exe", "query", "MySQL80"], capture_output=True, text=True)
    running = service.returncode == 0 and "RUNNING" in service.stdout
    checks.append(report("MySQL80 service", "PASS" if running else "FAIL", "running" if running else "not running"))

    if env and not missing:
        os.environ.update({key: str(value) for key, value in env.items() if value is not None})
        try:
            from app.database import backend_name, connect, init_db
            init_db()
            with connect() as con:
                row = con.execute("SELECT COUNT(*) AS count FROM events").fetchone()
            checks.append(report("MySQL application login", "PASS", f"backend={backend_name()}, events={row['count']}"))
        except Exception as error:
            checks.append(report("MySQL application login", "FAIL", str(error)))

    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            checks.append(report("FastAPI port 8000", "PASS", "server is listening"))
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as response:
            health = json.load(response)
        mysql_mode = health.get("database") == "mysql"
        checks.append(report("FastAPI database mode", "PASS" if mysql_mode else "FAIL", str(health)))
    except OSError:
        checks.append(report("FastAPI port 8000", "WARN", "not running; start with run.bat after setup"))

    model = ROOT / "jetson_agent" / "best.pt"
    checks.append(report("YOLO model", "PASS" if model.is_file() else "FAIL", f"{model} ({model.stat().st_size if model.exists() else 0} bytes)"))
    videos = sorted((ROOT / "video").glob("*.mp4"))
    checks.append(report("Test videos", "PASS" if videos else "FAIL", ", ".join(path.name for path in videos) or "none"))

    try:
        hostname = socket.gethostname()
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None, socket.AF_INET)})
        checks.append(report("LAN address candidates", "PASS" if addresses else "WARN", ", ".join(addresses) or "run network_check.bat"))
    except OSError as error:
        checks.append(report("LAN address candidates", "WARN", str(error)))

    print("=" * 52)
    failed = sum(not ok for ok in checks)
    print(f"Result: {len(checks) - failed}/{len(checks)} checks ready")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()

