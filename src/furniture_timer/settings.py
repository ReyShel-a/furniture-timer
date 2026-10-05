"""Typed application settings stored as key/value rows in sqlite."""

import logging
import math
import sqlite3
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

log = logging.getLogger(__name__)

DEFAULT_HOURLY_RATE = 0.0
DEFAULT_CURRENCY = "€"
DEFAULT_IDLE_THRESHOLD_SEC = 300

KEY_HOURLY_RATE = "hourly_rate"
KEY_CURRENCY = "currency"
KEY_IDLE_THRESHOLD_SEC = "idle_threshold_sec"


def parse_hourly_rate(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"hourly_rate must be a finite number >= 0, got {raw!r}")
    return value


def parse_currency(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("currency must not be empty")
    return value


def parse_idle_threshold(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise ValueError(f"idle_threshold_sec must be >= 1, got {raw!r}")
    return value


class Settings:
    """In-memory view of the settings table; call save() to persist changes."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._hourly_rate = DEFAULT_HOURLY_RATE
        self._currency = DEFAULT_CURRENCY
        self._idle_threshold_sec = DEFAULT_IDLE_THRESHOLD_SEC
        self.load()

    @property
    def hourly_rate(self) -> float:
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value: float) -> None:
        self._hourly_rate = parse_hourly_rate(str(value))

    @property
    def currency(self) -> str:
        return self._currency

    @currency.setter
    def currency(self, value: str) -> None:
        self._currency = parse_currency(value)

    @property
    def idle_threshold_sec(self) -> int:
        return self._idle_threshold_sec

    @idle_threshold_sec.setter
    def idle_threshold_sec(self, value: int) -> None:
        self._idle_threshold_sec = parse_idle_threshold(str(value))

    def load(self) -> None:
        """Read stored values; invalid or missing ones fall back to defaults."""
        rows: dict[str, str] = dict(self._conn.execute("SELECT key, value FROM settings"))
        self._hourly_rate = _read(rows, KEY_HOURLY_RATE, parse_hourly_rate, DEFAULT_HOURLY_RATE)
        self._currency = _read(rows, KEY_CURRENCY, parse_currency, DEFAULT_CURRENCY)
        self._idle_threshold_sec = _read(
            rows, KEY_IDLE_THRESHOLD_SEC, parse_idle_threshold, DEFAULT_IDLE_THRESHOLD_SEC
        )

    def save(self) -> None:
        values = {
            KEY_HOURLY_RATE: repr(self._hourly_rate),
            KEY_CURRENCY: self._currency,
            KEY_IDLE_THRESHOLD_SEC: str(self._idle_threshold_sec),
        }
        with self._conn:
            self._conn.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                values.items(),
            )


def _read(rows: dict[str, str], key: str, parse: Callable[[str], T], default: T) -> T:
    raw = rows.get(key)
    if raw is None:
        return default
    try:
        return parse(raw)
    except (TypeError, ValueError):
        log.warning("Invalid stored setting %s=%r; using default %r", key, raw, default)
        return default
