from datetime import datetime

import pytest

from furniture_timer.formatting import format_clock, format_hms


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


def test_format_clock_uses_local_time() -> None:
    ts = int(datetime(2026, 10, 5, 9, 7, 42).timestamp())
    assert format_clock(ts) == "09:07"
