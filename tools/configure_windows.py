from __future__ import annotations

import getpass
import os
import re
import secrets
import shutil
import sys
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
sys.path.insert(0, str(ROOT))


def safe_identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise ValueError(f"{label}에는 영문, 숫자, 밑줄만 사용할 수 있습니다.")
    return value


def main():
    print("EV Fire Guard Windows/MySQL setup")
    print("=" * 44)
    host = input("MySQL host [127.0.0.1]: ").strip() or "127.0.0.1"
    port = int(input("MySQL port [3306]: ").strip() or "3306")
    root_user = input("MySQL administrator [root]: ").strip() or "root"
    root_password = getpass.getpass("MySQL administrator password: ")
    database = safe_identifier(input("Database [ev_fire_guard]: ").strip() or "ev_fire_guard", "Database")
    app_user = safe_identifier(input("Application user [evguard]: ").strip() or "evguard", "Application user")
    app_password = getpass.getpass("Application password [Enter to generate]: ") or secrets.token_urlsafe(24)
    edge_token = secrets.token_urlsafe(32)

    connection = pymysql.connect(host=host, port=port, user=root_user, password=root_password, autocommit=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"CREATE USER IF NOT EXISTS '{app_user}'@'localhost' IDENTIFIED BY %s", (app_password,))
            cursor.execute(f"ALTER USER '{app_user}'@'localhost' IDENTIFIED BY %s", (app_password,))
            cursor.execute(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{app_user}'@'localhost'")
            cursor.execute("FLUSH PRIVILEGES")
    finally:
        connection.close()

    if ENV_PATH.exists():
        backup = ROOT / ".env.backup"
        shutil.copy2(ENV_PATH, backup)
        print(f"기존 .env 백업: {backup}")

    content = "\n".join(
        [
            "DATABASE_BACKEND=mysql",
            f"MYSQL_HOST={host}",
            f"MYSQL_PORT={port}",
            f"MYSQL_DATABASE={database}",
            f"MYSQL_USER={app_user}",
            f"MYSQL_PASSWORD={app_password}",
            f"EDGE_TOKEN={edge_token}",
            "",
        ]
    )
    ENV_PATH.write_text(content, encoding="utf-8")

    os.environ.update(
        DATABASE_BACKEND="mysql",
        MYSQL_HOST=host,
        MYSQL_PORT=str(port),
        MYSQL_DATABASE=database,
        MYSQL_USER=app_user,
        MYSQL_PASSWORD=app_password,
        EDGE_TOKEN=edge_token,
    )
    from app.database import init_db

    init_db()
    print("MySQL 데이터베이스, 테이블, .env 생성 완료")
    print("Jetson의 EDGE_TOKEN에는 Windows .env의 EDGE_TOKEN 값을 복사하세요.")
    print("다음 명령: run.bat")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n설정을 취소했습니다.")
        raise SystemExit(130)
    except Exception as error:
        print(f"\n[ERROR] 설정 실패: {error}")
        raise SystemExit(1)

