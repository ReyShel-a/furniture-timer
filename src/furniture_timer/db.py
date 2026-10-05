"""SQLite connection and schema migrations (tracked via PRAGMA user_version)."""

import logging
import sqlite3
from pathlib import Path

from furniture_timer import paths

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

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
}


class SchemaVersionError(RuntimeError):
    """Database was created by a newer app version."""


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
