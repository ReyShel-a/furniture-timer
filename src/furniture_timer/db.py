"""SQLite connection and schema migrations (tracked via PRAGMA user_version)."""

import logging
import sqlite3
from pathlib import Path
from typing import NamedTuple

from furniture_timer import paths

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2
HISTORY_LIMIT = 20

_SESSION_COLUMNS = (
    "id, start_ts, end_ts, active_seconds, idle_seconds, "
    "rate_snapshot, cost, note, project_number, project_name, client_name"
)

# Timestamps are unix epoch seconds (UTC); durations are whole seconds.
_MIGRATIONS: dict[int, str] = {
    1: """
        CREATE TABLE IF NOT EXISTS sessions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            start_ts       INTEGER NOT NULL,
            end_ts         INTEGER NOT NULL,
            active_seconds INTEGER NOT NULL,
            idle_seconds   INTEGER NOT NULL DEFAULT 0,
            rate_snapshot  REAL    NOT NULL,
            cost           REAL    NOT NULL,
            note           TEXT    NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """,
    2: """
        ALTER TABLE sessions ADD COLUMN project_number TEXT NOT NULL DEFAULT '';
        ALTER TABLE sessions ADD COLUMN project_name   TEXT NOT NULL DEFAULT '';
        ALTER TABLE sessions ADD COLUMN client_name    TEXT NOT NULL DEFAULT '';
    """,
}


class SchemaVersionError(RuntimeError):
    """Database was created by a newer app version."""


class SessionRow(NamedTuple):
    id: int
    start_ts: int
    end_ts: int
    active_seconds: int
    idle_seconds: int
    rate_snapshot: float
    cost: float
    note: str
    project_number: str
    project_name: str
    client_name: str


class ProjectRef(NamedTuple):
    """Latest stored name for one project number."""

    number: str
    name: str


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database (default: per-user data dir) and migrate it to SCHEMA_VERSION."""
    target = path if path is not None else paths.db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    try:
        migrate(conn)
    except Exception:
        conn.close()
        raise
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> None:
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Database schema v{current} is newer than supported v{SCHEMA_VERSION}"
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        conn.executescript(
            f"BEGIN;\n{_MIGRATIONS[version]}\nPRAGMA user_version = {version};\nCOMMIT;"
        )
        log.info("Migrated database schema to v%d", version)


def insert_session(
    conn: sqlite3.Connection,
    start_ts: int,
    end_ts: int,
    active_seconds: int,
    idle_seconds: int,
    rate_snapshot: float,
    cost: float,
    note: str = "",
    project_number: str = "",
    project_name: str = "",
    client_name: str = "",
) -> int:
    """Insert a finished session row. Returns the new row id."""
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions (
                start_ts, end_ts, active_seconds, idle_seconds,
                rate_snapshot, cost, note, project_number, project_name, client_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                start_ts,
                end_ts,
                active_seconds,
                idle_seconds,
                rate_snapshot,
                cost,
                note,
                project_number,
                project_name,
                client_name,
            ),
        )
    row_id = cursor.lastrowid
    if row_id is None:
        raise RuntimeError("INSERT INTO sessions did not produce a row id")
    return int(row_id)


def list_recent_sessions(
    conn: sqlite3.Connection, limit: int = HISTORY_LIMIT
) -> list[SessionRow]:
    """Return the newest sessions first, at most *limit* rows (never negative)."""
    capped = max(0, int(limit))
    rows = conn.execute(
        f"""
        SELECT {_SESSION_COLUMNS}
        FROM sessions
        ORDER BY id DESC
        LIMIT ?
        """,
        (capped,),
    ).fetchall()
    return [SessionRow(*row) for row in rows]


def list_known_projects(conn: sqlite3.Connection) -> list[ProjectRef]:
    """Project numbers with the name from the newest session of that number."""
    rows = conn.execute(
        """
        SELECT s.project_number, s.project_name
        FROM sessions AS s
        INNER JOIN (
            SELECT project_number, MAX(id) AS max_id
            FROM sessions
            WHERE TRIM(project_number) != ''
            GROUP BY project_number
        ) AS latest ON s.id = latest.max_id
        ORDER BY s.id DESC
        """
    ).fetchall()
    return [ProjectRef(str(number), str(name)) for number, name in rows]


def summarize_project(
    conn: sqlite3.Connection,
    project_number: str,
    start_ts: int,
    end_ts: int,
) -> tuple[int, float]:
    """Sum active time and cost for one project whose start falls in [start_ts, end_ts]."""
    row = conn.execute(
        """
        SELECT COALESCE(SUM(active_seconds), 0), COALESCE(SUM(cost), 0.0)
        FROM sessions
        WHERE project_number = ? AND start_ts >= ? AND start_ts <= ?
        """,
        (project_number, start_ts, end_ts),
    ).fetchone()
    if row is None:
        return (0, 0.0)
    return (int(row[0]), float(row[1]))


def clear_sessions(conn: sqlite3.Connection) -> None:
    """Delete every stored session. Settings are left untouched."""
    with conn:
        conn.execute("DELETE FROM sessions")


def list_known_clients(conn: sqlite3.Connection) -> list[str]:
    """Distinct client names, newest appearance first. Blanks are skipped."""
    rows = conn.execute(
        """
        SELECT client_name
        FROM sessions
        WHERE TRIM(client_name) != ''
        GROUP BY client_name
        ORDER BY MAX(id) DESC
        """
    ).fetchall()
    return [str(row[0]) for row in rows]
