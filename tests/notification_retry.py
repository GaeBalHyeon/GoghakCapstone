"""Telegram retry behavior without contacting Telegram."""

import os
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.notifications import send_telegram_alert


EVENT = {
    "event_type": "fire",
    "camera_id": "CAM-01",
    "floor": "B1",
    "zone": "충전구역 A",
    "confidence": 0.93,
    "detected_at": "2026-09-29T21:00:00+09:00",
}


def run() -> None:
    environment = {
        "TELEGRAM_ENABLED": "true",
        "TELEGRAM_BOT_TOKEN": "test-token",
        "TELEGRAM_CHAT_ID": "1234",
        "TELEGRAM_MAX_ATTEMPTS": "3",
    }
    failures = [urllib.error.URLError("offline"), urllib.error.URLError("offline"), None]

    def fake_post(*_args, **_kwargs):
        result = failures.pop(0)
        if result:
            raise result

    with patch.dict(os.environ, environment, clear=False), patch("app.notifications._post_form", side_effect=fake_post) as post, patch("app.notifications.time.sleep") as sleep:
        result = send_telegram_alert(EVENT, None)
        assert result.status == "sent"
        assert post.call_count == 3
        assert [call.args[0] for call in sleep.call_args_list] == [2, 5]

    bad_request = urllib.error.HTTPError("test", 400, "bad", {}, None)
    with patch.dict(os.environ, environment, clear=False), patch("app.notifications._post_form", side_effect=bad_request) as post, patch("app.notifications.time.sleep") as sleep:
        result = send_telegram_alert(EVENT, None)
        assert result.status == "failed"
        assert post.call_count == 1
        sleep.assert_not_called()

    print("Telegram retry and non-retryable error checks passed.")


if __name__ == "__main__":
    run()
