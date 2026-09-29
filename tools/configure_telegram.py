from __future__ import annotations

import getpass
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def telegram_call(token: str, method: str, fields: dict[str, str] | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode("utf-8") if fields is not None else None
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}", data=data, method="POST" if data else "GET"
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if not payload.get("ok"):
        raise RuntimeError("Telegram API 요청에 실패했습니다.")
    return payload


def update_env(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(values)
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if output and output[-1] != "":
        output.append("")
    output.extend(f"{key}={value}" for key, value in remaining.items())
    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> None:
    print("\nEV Fire Guard - Telegram 알림 설정")
    print("BotFather에서 만든 봇 토큰은 화면에 표시되지 않습니다.")
    token = getpass.getpass("봇 토큰: ").strip()
    if not token:
        raise SystemExit("토큰이 입력되지 않았습니다.")

    bot = telegram_call(token, "getMe")["result"]
    print(f"봇 확인: @{bot.get('username', 'unknown')}")
    print("휴대폰 Telegram에서 이 봇을 열고 /start를 보낸 뒤 Enter를 누르세요.")
    input()

    updates = telegram_call(token, "getUpdates").get("result", [])
    private_chats: dict[str, str] = {}
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") == "private" and chat.get("id") is not None:
            name = chat.get("first_name") or chat.get("username") or "개인 채팅"
            private_chats[str(chat["id"])] = str(name)
    if not private_chats:
        raise SystemExit("개인 채팅을 찾지 못했습니다. 봇에 /start를 보낸 뒤 다시 실행하세요.")

    chat_id, chat_name = list(private_chats.items())[-1]
    dashboard = input("홈페이지 주소 [http://192.168.0.223:8000]: ").strip() or "http://192.168.0.223:8000"
    update_env(
        {
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_CHAT_ID": chat_id,
            "DASHBOARD_URL": dashboard,
        }
    )
    telegram_call(
        token,
        "sendMessage",
        {"chat_id": chat_id, "text": "EV Fire Guard Telegram 알림 연결이 완료되었습니다."},
    )
    print(f"설정 완료: {chat_name} 채팅으로 테스트 메시지를 보냈습니다.")
    print("서버가 실행 중이면 stop.bat 후 start.bat로 다시 시작하세요.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"설정 실패: {type(error).__name__}. 토큰과 인터넷 연결을 확인하세요.") from None
