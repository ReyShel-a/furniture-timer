from datetime import datetime

import pytest

from furniture_timer.formatting import format_clock, format_datetime, format_hms, format_money


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00"),
        (59.999, "00:00:59"),
        (3661.9, "01:01:01"),
        (360_000, "100:00:00"),
        (-5, "00:00:00"),
    ],
)
def test_format_hms(seconds: float, expected: str) -> None:
    assert format_hms(seconds) == expected


def test_format_money_groups_thousands_and_appends_currency() -> None:
    assert format_money(1250.5, "₽") == "1 250.50 ₽"
    assert format_money(10, "EUR") == "10.00 EUR"


def test_format_clock_uses_local_time() -> None:
    ts = int(datetime(2026, 10, 5, 9, 7, 42).timestamp())
    assert format_clock(ts) == "09:07"


def test_format_datetime_uses_local_time() -> None:
    ts = int(datetime(2026, 10, 5, 9, 7, 42).timestamp())
    assert format_datetime(ts) == "2026-10-05 09:07"
