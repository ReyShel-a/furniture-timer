from collections.abc import Iterator

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from furniture_timer.formatting import format_clock
from furniture_timer.timer_model import TimerModel, TimerState
from furniture_timer.ui.controller import TICK_INTERVAL_MS, TimerController
from furniture_timer.ui.widget import TimerWidget

WALL_START = 1_700_000_000.0
RATE = 10.0
CURRENCY = "₽"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def wall(self) -> float:
        return WALL_START + self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class PriceSource:
    def __init__(self, rate: float = RATE, currency: str = CURRENCY) -> None:
        self.rate = rate
        self.currency = currency

    def hourly_rate(self) -> float:
        return self.rate

    def currency_code(self) -> str:
        return self.currency


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def model(clock: FakeClock) -> TimerModel:
    return TimerModel(clock=clock, wall_clock=clock.wall)


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def price() -> PriceSource:
    return PriceSource()


@pytest.fixture
def controller(
    model: TimerModel, widget: TimerWidget, price: PriceSource
) -> Iterator[TimerController]:
    c = TimerController(
        model, widget, hourly_rate=price.hourly_rate, currency=price.currency_code
    )
    yield c
    c.deleteLater()


def _time(widget: TimerWidget) -> str:
    label = widget.findChild(QLabel, "timeLabel")
    assert label is not None
    return label.text()


def _price(widget: TimerWidget) -> str:
    label = widget.findChild(QLabel, "priceLabel")
    assert label is not None
    return label.text()


def _button(widget: TimerWidget, name: str) -> QPushButton:
    button = widget.findChild(QPushButton, name)
    assert button is not None, name
    return button


def _click_start_pause(widget: TimerWidget) -> None:
    _button(widget, "startPauseButton").click()


def test_tick_interval_is_one_second() -> None:
    assert TICK_INTERVAL_MS == 1000


def test_initial_view(controller: TimerController, widget: TimerWidget) -> None:
    assert controller.is_ticking is False
    assert _time(widget) == "00:00:00"
    assert _price(widget) == "10.00 ₽/h  ·  0.00 ₽"
    assert _button(widget, "startPauseButton").text() == "Start"
    assert not _button(widget, "stopButton").isEnabled()


def test_tick_in_idle_keeps_zero(
    controller: TimerController, widget: TimerWidget, clock: FakeClock
) -> None:
    clock.advance(50)
    controller.tick()
    assert _time(widget) == "00:00:00"
    assert _price(widget) == "10.00 ₽/h  ·  0.00 ₽"


def test_start_runs_and_ticks(
    controller: TimerController, widget: TimerWidget, model: TimerModel, clock: FakeClock
) -> None:
    _click_start_pause(widget)

    assert model.state is TimerState.RUNNING
    assert controller.is_ticking is True
    assert _button(widget, "startPauseButton").text() == "Pause"
    assert _button(widget, "stopButton").isEnabled()
    assert widget.toolTip() == f"Session started at {format_clock(int(WALL_START))}"

    clock.advance(3661.9)
    controller.tick()
    assert _time(widget) == "01:01:01"
    assert _price(widget) == "10.00 ₽/h  ·  10.17 ₽"


def test_pause_freezes_and_resume_continues(
    controller: TimerController, widget: TimerWidget, clock: FakeClock
) -> None:
    _click_start_pause(widget)
    clock.advance(10)
    controller.tick()

    _click_start_pause(widget)
    assert controller.is_ticking is False
    assert _button(widget, "startPauseButton").text() == "Resume"
    clock.advance(100)
    controller.tick()
    assert _time(widget) == "00:00:10"
    assert _price(widget) == "10.00 ₽/h  ·  0.03 ₽"

    _click_start_pause(widget)
    assert controller.is_ticking is True
    assert _button(widget, "startPauseButton").text() == "Pause"
    clock.advance(5)
    controller.tick()
    assert _time(widget) == "00:00:15"
    assert _price(widget) == "10.00 ₽/h  ·  0.04 ₽"


def test_stop_resets_view(
    controller: TimerController, widget: TimerWidget, model: TimerModel, clock: FakeClock
) -> None:
    _click_start_pause(widget)
    clock.advance(42)
    controller.tick()

    _button(widget, "stopButton").click()

    assert controller.is_ticking is False
    assert model.state is TimerState.IDLE
    assert _time(widget) == "00:00:00"
    assert _price(widget) == "10.00 ₽/h  ·  0.00 ₽"
    assert _button(widget, "startPauseButton").text() == "Start"
    assert not _button(widget, "stopButton").isEnabled()
    assert widget.toolTip() == "No active session"


def test_stop_signal_in_idle_is_ignored(
    controller: TimerController, widget: TimerWidget, model: TimerModel
) -> None:
    widget.stop_clicked.emit()
    assert model.state is TimerState.IDLE
    assert controller.is_ticking is False


def test_tick_updates_live_cost(
    controller: TimerController, widget: TimerWidget, clock: FakeClock
) -> None:
    _click_start_pause(widget)
    clock.advance(3600)
    controller.tick()
    assert _price(widget) == "10.00 ₽/h  ·  10.00 ₽"


def test_pause_freezes_cost(
    controller: TimerController, widget: TimerWidget, clock: FakeClock
) -> None:
    _click_start_pause(widget)
    clock.advance(3600)
    controller.tick()
    _click_start_pause(widget)

    clock.advance(3600)
    controller.tick()
    assert _time(widget) == "01:00:00"
    assert _price(widget) == "10.00 ₽/h  ·  10.00 ₽"


def test_live_rate_change_applies_on_next_tick(
    controller: TimerController,
    widget: TimerWidget,
    clock: FakeClock,
    price: PriceSource,
) -> None:
    _click_start_pause(widget)
    clock.advance(3600)
    controller.tick()
    assert _price(widget) == "10.00 ₽/h  ·  10.00 ₽"

    price.rate = 20.0
    price.currency = "$"
    controller.tick()
    assert _price(widget) == "20.00 $/h  ·  20.00 $"


def test_auto_pause_rolls_cost_back(
    controller: TimerController,
    widget: TimerWidget,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    _click_start_pause(widget)
    clock.advance(3600)
    controller.tick()
    assert _price(widget) == "10.00 ₽/h  ·  10.00 ₽"

    model.auto_pause(1800)
    controller.refresh()
    assert _time(widget) == "00:30:00"
    assert _price(widget) == "10.00 ₽/h  ·  5.00 ₽"


def test_real_qtimer_drives_tick(
    model: TimerModel, widget: TimerWidget, clock: FakeClock
) -> None:
    c = TimerController(model, widget, interval_ms=20)
    try:
        _click_start_pause(widget)
        clock.advance(2)
        QTest.qWait(100)
        assert _time(widget) == "00:00:02"
    finally:
        c.deleteLater()
