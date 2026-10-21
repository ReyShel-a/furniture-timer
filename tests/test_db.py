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
    "finalized",
]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_fresh_db_has_current_schema(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        assert db.schema_version(conn) == db.SCHEMA_VERSION == 3
        assert _columns(conn, "sessions") == SESSIONS_COLUMNS
        assert _columns(conn, "settings") == ["key", "value"]
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert conn.execute("PRAGMA synchronous").fetchone() == (2,)
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
        assert db.schema_version(conn) == db.SCHEMA_VERSION
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
        assert db.schema_version(conn) == db.SCHEMA_VERSION
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


def test_projects_for_client_keep_that_clients_latest_name(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        db.insert_session(
            conn, 1, 2, 1, 0, 0.0, 0.0, project_number="12", project_name="Kitchen", client_name="Ivan"
        )
        db.insert_session(
            conn, 3, 4, 1, 0, 0.0, 0.0, project_number="12", project_name="Wardrobe", client_name="Ivan"
        )
        db.insert_session(
            conn, 5, 6, 1, 0, 0.0, 0.0, project_number="9", project_name="Hall", client_name="Ivan"
        )
        db.insert_session(
            conn, 7, 8, 1, 0, 0.0, 0.0, project_number="12", project_name="Other", client_name="Anna"
        )
        db.insert_session(
            conn, 9, 10, 1, 0, 0.0, 0.0, project_number="7", project_name="Kitchen", client_name="Anna"
        )
        db.insert_session(conn, 11, 12, 1, 0, 0.0, 0.0, project_name="Skip", client_name="Ivan")
        assert db.list_projects_for_client(conn, "Ivan") == [
            db.ProjectRef("9", "Hall"),
            db.ProjectRef("12", "Wardrobe"),
        ]
        assert db.list_projects_for_client(conn, "Anna") == [
            db.ProjectRef("7", "Kitchen"),
            db.ProjectRef("12", "Other"),
        ]
        assert db.list_projects_for_client(conn, " ") == []
        assert db.list_projects_for_client(conn, "Nobody") == []
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


def test_v2_database_gains_finalized_column(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    raw = sqlite3.connect(path)
    raw.executescript(db._MIGRATIONS[1])
    raw.executescript(db._MIGRATIONS[2])
    raw.execute("PRAGMA user_version = 2")
    raw.execute(
        "INSERT INTO sessions (start_ts, end_ts, active_seconds, rate_snapshot, cost) "
        "VALUES (10, 20, 5, 1.0, 2.0)"
    )
    raw.commit()
    raw.close()

    conn = db.connect(path)
    try:
        assert db.schema_version(conn) == db.SCHEMA_VERSION
        assert _columns(conn, "sessions") == SESSIONS_COLUMNS
        assert conn.execute("SELECT finalized FROM sessions").fetchone() == (1,)
        assert [row.id for row in db.list_recent_sessions(conn)] == [1]
    finally:
        conn.close()


def test_open_session_stays_hidden_until_finalized(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        open_id = db.save_session(
            conn, None, 10, 20, 5, 1, 20.0, 1.0, finalized=False, project_number="7"
        )
        finished = db.insert_session(
            conn, 30, 40, 9, 0, 0.0, 2.0, project_number="7"
        )
        assert open_id == 1
        assert [row.id for row in db.list_recent_sessions(conn)] == [finished]
        assert db.summarize_project(conn, "7", 0, 100) == (9, 2.0)

        assert (
            db.save_session(
                conn, open_id, 10, 50, 15, 1, 20.0, 3.0, finalized=False, project_number="7"
            )
            == open_id
        )
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone() == (2,)
        assert conn.execute(
            "SELECT end_ts, active_seconds, cost, finalized FROM sessions WHERE id = 1"
        ).fetchone() == (50, 15, 3.0, 0)

        assert db.finalize_open_sessions(conn) == 1
        assert db.finalize_open_sessions(conn) == 0
        assert [row.id for row in db.list_recent_sessions(conn)] == [finished, open_id]
        assert db.summarize_project(conn, "7", 0, 100) == (24, 5.0)
    finally:
        conn.close()


def test_list_sessions_between_is_inclusive_and_skips_open(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        db.insert_session(conn, 100, 110, 1, 0, 0.0, 1.0)
        db.insert_session(conn, 100, 110, 2, 0, 0.0, 2.0)
        db.insert_session(conn, 50, 60, 3, 0, 0.0, 3.0)
        db.insert_session(conn, 200, 210, 4, 0, 0.0, 4.0)
        open_id = db.save_session(
            conn, None, 150, 160, 5, 0, 0.0, 5.0, finalized=False
        )
        assert [row.id for row in db.list_sessions_between(conn, 100, 200)] == [4, 2, 1]
        assert [row.id for row in db.list_sessions_between(conn, 201, 300)] == []
        assert open_id == 5
    finally:
        conn.close()


def test_delete_sessions_keeps_open_rows_settings_and_others(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        finished = db.insert_session(conn, 100, 110, 1, 0, 0.0, 1.0, project_number="7")
        kept = db.insert_session(conn, 200, 210, 2, 0, 0.0, 2.0, project_number="12")
        open_id = db.save_session(
            conn, None, 150, 160, 5, 0, 0.0, 5.0, finalized=False, project_number="7"
        )
        with conn:
            conn.execute("INSERT INTO settings (key, value) VALUES ('hourly_rate', '20')")
        db.delete_sessions(conn, [])
        db.delete_sessions(conn, [finished, open_id, 999])
        assert [row.id for row in db.list_recent_sessions(conn)] == [kept]
        assert conn.execute(
            "SELECT id, finalized FROM sessions WHERE id = ?", (open_id,)
        ).fetchone() == (open_id, 0)
        assert conn.execute("SELECT value FROM settings WHERE key = 'hourly_rate'").fetchone() == (
            "20",
        )
    finally:
        conn.close()


def test_save_session_inserts_when_the_row_is_gone(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        row_id = db.save_session(conn, None, 1, 2, 1, 0, 0.0, 0.0, finalized=False)
        db.clear_sessions(conn)
        replaced = db.save_session(
            conn, row_id, 1, 9, 8, 0, 0.0, 1.0, finalized=True
        )
        assert replaced != row_id
        assert conn.execute(
            "SELECT id, active_seconds, finalized FROM sessions"
        ).fetchone() == (replaced, 8, 1)
    finally:
        conn.close()
