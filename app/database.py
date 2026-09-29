from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA = ROOT / "data"
SQLITE_PATH = DATA / "ev_fire_guard.db"


class Connection:
    def __init__(self):
        self.mysql = os.getenv("DATABASE_BACKEND", "sqlite").lower() == "mysql"
        if self.mysql:
            import pymysql

            self.raw = pymysql.connect(
                host=os.getenv("MYSQL_HOST", "127.0.0.1"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "evguard"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "ev_fire_guard"),
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
        else:
            DATA.mkdir(exist_ok=True)
            self.raw = sqlite3.connect(SQLITE_PATH)
            self.raw.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()):
        if self.mysql:
            cursor = self.raw.cursor()
            cursor.execute(sql.replace("?", "%s"), params)
            return cursor
        return self.raw.execute(sql, params)

    def executescript(self, script: str):
        if self.mysql:
            for statement in script.split(";"):
                if statement.strip():
                    self.execute(statement)
            return
        self.raw.executescript(script)

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _tb):
        if exc_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.raw.close()


def connect() -> Connection:
    return Connection()


def init_db() -> None:
    DATA.mkdir(exist_ok=True)
    mysql = os.getenv("DATABASE_BACKEND", "sqlite").lower() == "mysql"
    with connect() as con:
        if mysql:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    camera_id VARCHAR(40) NOT NULL,
                    floor VARCHAR(20) NOT NULL,
                    zone VARCHAR(100) NOT NULL,
                    charger VARCHAR(100) NOT NULL,
                    event_type VARCHAR(20) NOT NULL,
                    confidence DOUBLE NOT NULL,
                    source VARCHAR(50) NOT NULL,
                    detected_at VARCHAR(40) NOT NULL,
                    resolved_at VARCHAR(40) NULL,
                    resolution_note VARCHAR(255) NULL,
                    snapshot_path VARCHAR(255) NULL,
                    notification_status VARCHAR(20) NULL,
                    notification_error TEXT NULL,
                    notified_at VARCHAR(40) NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    id INT PRIMARY KEY,
                    simulation_enabled TINYINT NOT NULL DEFAULT 0,
                    auto_event_interval INT NOT NULL DEFAULT 45
                );
                """
            )
            con.execute(
                "INSERT IGNORE INTO settings(id, simulation_enabled, auto_event_interval) VALUES (1, 0, 45)"
            )
            for name, definition in (
                ("snapshot_path", "VARCHAR(255) NULL"),
                ("notification_status", "VARCHAR(20) NULL"),
                ("notification_error", "TEXT NULL"),
                ("notified_at", "VARCHAR(40) NULL"),
            ):
                if not con.execute("SHOW COLUMNS FROM events LIKE ?", (name,)).fetchone():
                    con.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")
        else:
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
                    resolution_note TEXT,
                    snapshot_path TEXT,
                    notification_status TEXT,
                    notification_error TEXT,
                    notified_at TEXT
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
            existing = {row["name"] for row in con.execute("PRAGMA table_info(events)").fetchall()}
            for name in ("snapshot_path", "notification_status", "notification_error", "notified_at"):
                if name not in existing:
                    con.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT")


def backend_name() -> str:
    return os.getenv("DATABASE_BACKEND", "sqlite").lower()

