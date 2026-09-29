"""Run after configure_windows.bat to verify the configured MySQL database."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import backend_name, connect, init_db


def main():
    if backend_name() != "mysql":
        raise SystemExit("DATABASE_BACKEND is not mysql. Run configure_windows.bat first.")
    init_db()
    marker = "mysql-integration-check"
    with connect() as con:
        cursor = con.execute(
            """
            INSERT INTO events(camera_id, floor, zone, charger, event_type,
                               confidence, source, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("TEST", "B1", "DB check", "-", "smoke", 0.99, marker, "2000-01-01T00:00:00+00:00"),
        )
        event_id = cursor.lastrowid
        row = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        assert row["source"] == marker
        con.execute("DELETE FROM events WHERE id=?", (event_id,))
    print("MySQL connection, schema, insert, select, and cleanup checks passed.")


if __name__ == "__main__":
    main()

