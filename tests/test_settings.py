import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from furniture_timer import db
from furniture_timer.i18n import system_language
from furniture_timer.settings import (
    DEFAULT_CURRENCY,
    DEFAULT_HOURLY_RATE,
    DEFAULT_IDLE_THRESHOLD_SEC,
    DEFAULT_LANGUAGE,
    Settings,
)


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = db.connect(tmp_path / "db.sqlite")
    yield connection
    connection.close()


def test_defaults_on_empty_db(conn: sqlite3.Connection) -> None:
    settings = Settings(conn)

    assert settings.hourly_rate == DEFAULT_HOURLY_RATE == 0.0
    assert settings.currency == DEFAULT_CURRENCY == "₽"
    assert settings.idle_threshold_sec == DEFAULT_IDLE_THRESHOLD_SEC == 300
    assert settings.language == system_language()


def test_save_and_load_roundtrip(conn: sqlite3.Connection) -> None:
    settings = Settings(conn)
    settings.hourly_rate = 42.5
    settings.currency = "$"
    settings.idle_threshold_sec = 120
    settings.language = "ru"
    settings.save()

    reloaded = Settings(conn)
    assert reloaded.hourly_rate == 42.5
    assert reloaded.currency == "$"
    assert reloaded.idle_threshold_sec == 120
    assert reloaded.language == "ru"


def test_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "reopen.sqlite"
    first = db.connect(path)
    settings = Settings(first)
    settings.hourly_rate = 0.1
    settings.save()
    first.close()

    second = db.connect(path)
    try:
        assert Settings(second).hourly_rate == 0.1
    finally:
        second.close()


def test_invalid_stored_values_fall_back_to_defaults(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
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
        ("language", "de"),
    ],
)
def test_setters_reject_invalid_values(
    conn: sqlite3.Connection, field: str, value: object
) -> None:
    settings = Settings(conn)
    with pytest.raises(ValueError):
        setattr(settings, field, value)


def test_missing_language_follows_system(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("furniture_timer.settings.system_language", lambda: "ru")

    assert Settings(conn).language == "ru"


def test_invalid_language_falls_back_to_english(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("language", "de"))

    settings = Settings(conn)

    assert settings.language == DEFAULT_LANGUAGE == "en"
    assert "Invalid stored setting" in caplog.text
