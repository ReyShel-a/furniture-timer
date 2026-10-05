import sqlite3
from pathlib import Path

import pytest

from furniture_timer import db, paths

SESSIONS_COLUMNS = [
    "id",
    "start_ts",
    "end_ts",
    "active_seconds",
    "idle_seconds",
    "rate_snapshot",
    "cost",
    "note",
]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_fresh_db_has_schema_v1(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        assert db.schema_version(conn) == db.SCHEMA_VERSION == 1
        assert _columns(conn, "sessions") == SESSIONS_COLUMNS
        assert _columns(conn, "settings") == ["key", "value"]
    finally:
        conn.close()


def test_reopen_is_idempotent_and_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    conn = db.connect(path)
    with conn:
        conn.execute(
            "INSERT INTO sessions (start_ts, end_ts, active_seconds, rate_snapshot, cost) "
            "VALUES (1000, 4600, 3600, 50.0, 50.0)"
        )
    conn.close()

    conn = db.connect(path)
    try:
        assert db.schema_version(conn) == 1
        row = conn.execute(
            "SELECT active_seconds, idle_seconds, cost, note FROM sessions"
        ).fetchone()
        assert row == (3600, 0, 50.0, "")
    finally:
        conn.close()


def test_default_path_comes_from_paths_and_creates_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "FurnitureTimer" / "db.sqlite"
    monkeypatch.setattr(paths, "db_path", lambda: target)

    conn = db.connect()
    conn.close()

    assert target.is_file()


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 99")
    raw.close()

    with pytest.raises(db.SchemaVersionError):
        db.connect(path)
