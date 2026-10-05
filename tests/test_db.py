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
    "project_number",
    "project_name",
    "client_name",
]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_fresh_db_has_schema_v2(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        assert db.schema_version(conn) == db.SCHEMA_VERSION == 2
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
        assert db.schema_version(conn) == 2
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


def _session_row(conn: sqlite3.Connection, row_id: int) -> tuple[object, ...]:
    return conn.execute(
        "SELECT id, start_ts, end_ts, active_seconds, idle_seconds, "
        "rate_snapshot, cost, note, project_number, project_name, client_name "
        "FROM sessions WHERE id = ?",
        (row_id,),
    ).fetchone()


def test_insert_session_writes_all_columns(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        row_id = db.insert_session(
            conn,
            start_ts=1000,
            end_ts=2800,
            active_seconds=1800,
            idle_seconds=120,
            rate_snapshot=20.0,
            cost=10.0,
            note="cut list",
            project_number="12",
            project_name="Kitchen",
            client_name="Ivan",
        )
        assert row_id == 1
        assert _session_row(conn, row_id) == (
            1,
            1000,
            2800,
            1800,
            120,
            20.0,
            10.0,
            "cut list",
            "12",
            "Kitchen",
            "Ivan",
        )
    finally:
        conn.close()


def test_insert_session_defaults_note_and_appends_rows(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        first = db.insert_session(conn, 1, 2, 0, 0, 0.0, 0.0)
        second = db.insert_session(conn, 10, 20, 5, 1, 50.0, 10.0)
        assert first == 1
        assert second == 2
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone() == (2,)
        assert _session_row(conn, first)[7:] == ("", "", "", "")
        assert _session_row(conn, second) == (2, 10, 20, 5, 1, 50.0, 10.0, "", "", "", "")
    finally:
        conn.close()


def test_list_recent_sessions_empty(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        assert db.list_recent_sessions(conn) == []
    finally:
        conn.close()


def test_list_recent_sessions_newest_first_capped_at_20(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        for i in range(1, 26):
            db.insert_session(conn, i, i + 1, i, 0, 0.0, float(i))
        rows = db.list_recent_sessions(conn)
        assert len(rows) == db.HISTORY_LIMIT == 20
        assert [row.id for row in rows] == list(range(25, 5, -1))
        assert rows[0] == db.SessionRow(25, 25, 26, 25, 0, 0.0, 25.0, "", "", "", "")
        assert rows[-1].id == 6
    finally:
        conn.close()


def test_list_recent_sessions_honors_limit(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        db.insert_session(conn, 1, 2, 1, 0, 0.0, 0.0)
        db.insert_session(conn, 3, 4, 2, 0, 0.0, 0.0)
        db.insert_session(conn, 5, 6, 3, 0, 0.0, 0.0)
        rows = db.list_recent_sessions(conn, limit=2)
        assert [row.id for row in rows] == [3, 2]
        assert db.list_recent_sessions(conn, limit=0) == []
        assert db.list_recent_sessions(conn, limit=-1) == []
    finally:
        conn.close()


def test_v1_database_gains_empty_job_columns(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(db._MIGRATIONS[1])
    raw.execute("PRAGMA user_version = 1")
    raw.execute(
        "INSERT INTO sessions (start_ts, end_ts, active_seconds, rate_snapshot, cost) "
        "VALUES (10, 20, 5, 1.0, 2.0)"
    )
    raw.commit()
    raw.close()

    conn = db.connect(path)
    try:
        assert db.schema_version(conn) == 2
        assert _columns(conn, "sessions") == SESSIONS_COLUMNS
        row = db.list_recent_sessions(conn)[0]
        assert (row.project_number, row.project_name, row.client_name) == ("", "", "")
    finally:
        conn.close()


def test_known_projects_use_latest_name_and_skip_blanks(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        db.insert_session(
            conn, 1, 2, 1, 0, 0.0, 0.0, project_number="12", project_name="Kitchen", client_name="Ivan"
        )
        db.insert_session(
            conn, 3, 4, 1, 0, 0.0, 0.0, project_number="12", project_name="Wardrobe", client_name="Ivan"
        )
        db.insert_session(
            conn, 5, 6, 1, 0, 0.0, 0.0, project_number="7", project_name="Kitchen", client_name="Anna"
        )
        db.insert_session(conn, 7, 8, 1, 0, 0.0, 0.0, project_name="Skip", client_name="  ")
        assert db.list_known_projects(conn) == [
            db.ProjectRef("7", "Kitchen"),
            db.ProjectRef("12", "Wardrobe"),
        ]
        assert db.list_known_clients(conn) == ["Anna", "Ivan"]
    finally:
        conn.close()


def test_summarize_project_filters_number_and_range(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        db.insert_session(
            conn, 1000, 1100, 10, 0, 0.0, 1.5, project_number="7"
        )
        db.insert_session(
            conn, 2000, 2100, 20, 0, 0.0, 2.5, project_number="7"
        )
        db.insert_session(
            conn, 1500, 1600, 100, 0, 0.0, 9.0, project_number="12"
        )
        db.insert_session(
            conn, 50, 60, 5, 0, 0.0, 1.0, project_number="7"
        )
        assert db.summarize_project(conn, "7", 1000, 2000) == (30, 4.0)
        assert db.summarize_project(conn, "7", 0, 10) == (0, 0.0)
        assert db.summarize_project(conn, "missing", 0, 5000) == (0, 0.0)
    finally:
        conn.close()
