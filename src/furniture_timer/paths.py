"""Filesystem locations for application data and logs."""

from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "FurnitureTimer"
DB_FILENAME = "db.sqlite"
LOG_FILENAME = "app.log"


def data_dir() -> Path:
    """Per-user data directory, e.g. %APPDATA%/FurnitureTimer on Windows."""
    return Path(user_data_dir(APP_NAME, appauthor=False, roaming=True))


def log_dir() -> Path:
    return data_dir() / "logs"


def db_path() -> Path:
    return data_dir() / DB_FILENAME
