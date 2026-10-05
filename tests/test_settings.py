import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from furniture_timer.settings import (
    DEFAULT_CURRENCY,
    DEFAULT_HOURLY_RATE,
    DEFAULT_IDLE_THRESHOLD_SEC,
    Settings,
)


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_defaults_on_empty_db(conn: sqlite3.Connection) -> None:
    settings = Settings(conn)

    assert settings.hourly_rate == DEFAULT_HOURLY_RATE == 0.0
    assert settings.currency == DEFAULT_CURRENCY == "€"
    assert settings.idle_threshold_sec == DEFAULT_IDLE_THRESHOLD_SEC == 300


def test_save_and_load_roundtrip(conn: sqlite3.Connection) -> None:
    settings = Settings(conn)
    settings.hourly_rate = 42.5
    settings.currency = "₽"
    settings.idle_threshold_sec = 120
    settings.save()

    reloaded = Settings(conn)
    assert reloaded.hourly_rate == 42.5
    assert reloaded.currency == "₽"
    assert reloaded.idle_threshold_sec == 120


def test_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    first = sqlite3.connect(path)
    settings = Settings(first)
    settings.hourly_rate = 0.1
    settings.save()
    first.close()

    second = sqlite3.connect(path)
    try:
        assert Settings(second).hourly_rate == 0.1
    finally:
        second.close()


def test_invalid_stored_values_fall_back_to_defaults(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    Settings(conn)
    conn.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        [("hourly_rate", "abc"), ("currency", "   "), ("idle_threshold_sec", "0")],
    )

    settings = Settings(conn)

    assert settings.hourly_rate == DEFAULT_HOURLY_RATE
    assert settings.currency == DEFAULT_CURRENCY
    assert settings.idle_threshold_sec == DEFAULT_IDLE_THRESHOLD_SEC
    assert caplog.text.count("Invalid stored setting") == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hourly_rate", -1.0),
        ("hourly_rate", float("nan")),
        ("currency", ""),
        ("idle_threshold_sec", 0),
    ],
)
def test_setters_reject_invalid_values(
    conn: sqlite3.Connection, field: str, value: object
) -> None:
    settings = Settings(conn)
    with pytest.raises(ValueError):
        setattr(settings, field, value)
