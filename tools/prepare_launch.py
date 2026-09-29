from __future__ import annotations

import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
LAUNCH_URL_PATH = ROOT / "data" / "launch_url.txt"


def current_lan_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        address = probe.getsockname()[0]
        if address and not address.startswith("127."):
            return address
    except OSError:
        pass
    finally:
        probe.close()
    for address in socket.gethostbyname_ex(socket.gethostname())[2]:
        if not address.startswith(("127.", "169.254.")):
            return address
    return "127.0.0.1"


def update_dashboard_url(url: str) -> None:
    if not ENV_PATH.exists():
        raise FileNotFoundError(".env is missing. Run configure_windows.bat first.")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    updated = False
    for line in lines:
        if line.startswith("DASHBOARD_URL="):
            output.append(f"DASHBOARD_URL={url}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.extend(["", f"DASHBOARD_URL={url}"])
    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")


def port_is_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.4)
        return client.connect_ex(("127.0.0.1", 8000)) == 0


def main() -> int:
    ip = current_lan_ip()
    dashboard = f"http://{ip}:8000"
    LAUNCH_URL_PATH.parent.mkdir(exist_ok=True)
    LAUNCH_URL_PATH.write_text(dashboard + "\n", encoding="utf-8")
    if "--print-url" in sys.argv:
        print(dashboard)
        return 0
    update_dashboard_url(dashboard)
    print(f"[NETWORK] Windows LAN address: {ip}")
    print(f"[NETWORK] Mobile dashboard: {dashboard}")
    print("[NETWORK] If Jetson cannot connect at a new venue, set the Windows network profile to Private.")
    if port_is_open():
        return 10
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"[ERROR] {error}")
        raise SystemExit(1) from None
