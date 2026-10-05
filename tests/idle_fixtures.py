"""Pytest fixtures for idle dialog/controller tests."""

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from furniture_timer.timer_model import TimerModel
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.idle_controller import IdleController
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.widget import TimerWidget
from tests.idle_support import THRESHOLD, FakeClock, FakeIdleDetector


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
def dialog(widget: TimerWidget) -> Iterator[IdleDialog]:
    d = IdleDialog(widget)
    yield d
    d.hide()
    d.close()
    d.deleteLater()


@pytest.fixture
def detector() -> FakeIdleDetector:
    return FakeIdleDetector()


@pytest.fixture
def timer_controller(model: TimerModel, widget: TimerWidget) -> Iterator[TimerController]:
    c = TimerController(model, widget)
    yield c
    c.deleteLater()


@pytest.fixture
def idle_controller(
    model: TimerModel,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    timer_controller: TimerController,
) -> Iterator[IdleController]:
    c = IdleController(
        model,
        widget,
        dialog,
        detector,
        threshold=lambda: THRESHOLD,
        timer_controller=timer_controller,
        interval_ms=60_000,
    )
    yield c
    c.deleteLater()
