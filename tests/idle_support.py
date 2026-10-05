"""Shared fakes and helpers for idle-flow tests."""

from PySide6.QtWidgets import QLabel, QPushButton

from furniture_timer.timer_model import TimerModel
from furniture_timer.ui.idle_controller import IdleController
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.widget import TimerWidget

WALL_START = 1_700_000_000.0
THRESHOLD = 300.0
WORK = 100.0


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def wall(self) -> float:
        return WALL_START + self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeIdleDetector:
    def __init__(self) -> None:
        self.reading: float | None = 0.0

    @property
    def available(self) -> bool:
        return self.reading is not None

    def idle_seconds(self) -> float | None:
        return self.reading

    def stop(self) -> None:
        pass


def button(root: TimerWidget | IdleDialog, name: str) -> QPushButton:
    found = root.findChild(QPushButton, name)
    assert found is not None, name
    return found


def message(dialog: IdleDialog) -> str:
    label = dialog.findChild(QLabel, "idleMessage")
    assert label is not None
    return label.text()


def start(widget: TimerWidget) -> None:
    button(widget, "startPauseButton").click()


def enter_auto_pause(
    widget: TimerWidget,
    clock: FakeClock,
    detector: FakeIdleDetector,
    idle_controller: IdleController,
    work: float = WORK,
    idle_sec: float = THRESHOLD,
) -> None:
    start(widget)
    clock.advance(work + idle_sec)
    detector.reading = idle_sec
    idle_controller.poll()