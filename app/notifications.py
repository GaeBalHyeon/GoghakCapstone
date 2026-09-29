from __future__ import annotations

import html
import json
import mimetypes
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class NotificationResult:
    status: str
    error: str | None = None
    notified_at: str | None = None


def telegram_configured() -> bool:
    return (
        os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
        and bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
        and bool(os.getenv("TELEGRAM_CHAT_ID", "").strip())
    )


def _caption(event: dict) -> str:
    event_label = "화재" if event["event_type"] == "fire" else "연기"
    icon = "🚨" if event["event_type"] == "fire" else "⚠️"
    dashboard = os.getenv("DASHBOARD_URL", "http://127.0.0.1:8000").strip()
    return "\n".join(
        [
            f"{icon} <b>{event_label} 감지</b>",
            "",
            f"카메라: <b>{html.escape(str(event['camera_id']))}</b>",
            f"위치: {html.escape(str(event['floor']))} {html.escape(str(event['zone']))}",
            f"신뢰도: {float(event['confidence']) * 100:.1f}%",
            f"감지 시각: {html.escape(str(event['detected_at']))}",
            "",
            f'<a href="{html.escape(dashboard, quote=True)}">관제 페이지 열기</a>',
        ]
    )


def _post_form(url: str, fields: dict[str, str]) -> None:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram API returned ok=false")


def _post_photo(url: str, fields: dict[str, str], photo_path: Path) -> None:
    boundary = "----EVFireGuard" + secrets.token_hex(12)
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime = mimetypes.guess_type(photo_path.name)[0] or "image/jpeg"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="photo"; filename="{photo_path.name}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            photo_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram API returned ok=false")


def send_telegram_alert(event: dict, snapshot_path: Path | None) -> NotificationResult:
    if not telegram_configured():
        return NotificationResult(status="disabled")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    caption = _caption(event)
    base_url = f"https://api.telegram.org/bot{token}"
    max_attempts = min(max(int(os.getenv("TELEGRAM_MAX_ATTEMPTS", "3")), 1), 5)
    retry_delays = (2, 5, 10, 20)
    last_error = "Telegram 전송 실패"

    for attempt in range(1, max_attempts + 1):
        try:
            if snapshot_path and snapshot_path.is_file():
                _post_photo(
                    f"{base_url}/sendPhoto",
                    {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                    snapshot_path,
                )
            else:
                _post_form(
                    f"{base_url}/sendMessage",
                    {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"},
                )
            return NotificationResult(
                status="sent",
                notified_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            )
        except urllib.error.HTTPError as error:
            last_error = f"Telegram HTTP {error.code} ({attempt}/{max_attempts})"
            retryable = error.code == 429 or error.code >= 500
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = f"Telegram connection error: {type(error).__name__} ({attempt}/{max_attempts})"
            retryable = True
        except Exception as error:
            last_error = f"Telegram error: {type(error).__name__} ({attempt}/{max_attempts})"
            retryable = False

        if not retryable or attempt >= max_attempts:
            break
        time.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])

    return NotificationResult(status="failed", error=last_error)
