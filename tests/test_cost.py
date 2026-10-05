import pytest

from furniture_timer.cost import live_cost


@pytest.mark.parametrize(
    ("seconds", "rate", "expected"),
    [
        (0, 10.0, 0.0),
        (3600, 10.0, 10.0),
        (1800, 20.0, 10.0),
        (3600, 0.0, 0.0),
        (-5, 10.0, 0.0),
    ],
)
def test_live_cost(seconds: float, rate: float, expected: float) -> None:
    assert live_cost(seconds, rate) == expected
