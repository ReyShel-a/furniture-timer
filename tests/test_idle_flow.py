from PySide6.QtTest import QTest

from furniture_timer.formatting import format_hms
from furniture_timer.i18n import t
from furniture_timer.timer_model import TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.idle_controller import IDLE_POLL_INTERVAL_MS, IdleController
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.widget import TimerWidget
from tests.idle_support import (
    THRESHOLD,
    WORK,
    FakeClock,
    FakeIdleDetector,
    button,
    enter_auto_pause,
    message,
    start,
)


def test_poll_interval_is_one_second() -> None:
    assert IDLE_POLL_INTERVAL_MS == 1000


def test_below_threshold_stays_running(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
) -> None:
    start(widget)
    detector.reading = 10
    idle_controller.poll()
    assert model.state is TimerState.RUNNING
    assert not dialog.isVisible()


def test_threshold_auto_pauses_and_shows_alert(
    idle_controller: IdleController,
    timer_controller: TimerController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)

    assert model.state is TimerState.AUTO_PAUSED
    assert model.active_seconds == WORK
    assert model.pending_idle_seconds == THRESHOLD
    assert timer_controller.is_ticking is False
    assert idle_controller.is_polling is True
    assert dialog.isVisible()
    assert dialog.is_on_screen()
    assert not dialog.is_prompt
    assert message(dialog) == t("idle.dialog.message", duration=format_hms(THRESHOLD))


def test_polls_grow_peak_and_return_does_not_shrink_it(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    clock.advance(50)
    detector.reading = THRESHOLD + 50
    idle_controller.poll()

    assert model.pending_idle_seconds == THRESHOLD + 50
    assert message(dialog) == t("idle.dialog.message", duration=format_hms(THRESHOLD + 50))

    detector.reading = 0
    idle_controller.poll()
    assert model.pending_idle_seconds == THRESHOLD + 50
    assert not dialog.is_prompt
    assert dialog.isVisible()


def test_keep_pauses_records_peak_and_never_prompts(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    peak = model.pending_idle_seconds
    button(dialog, "keepButton").click()

    assert model.state is TimerState.PAUSED
    assert model.idle_seconds == peak
    assert not dialog.isVisible()
    assert idle_controller.is_polling is False

    detector.reading = 0
    idle_controller.poll()
    assert not dialog.isVisible()
    assert model.state is TimerState.PAUSED


def test_resume_runs_and_records_peak(
    idle_controller: IdleController,
    timer_controller: TimerController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    peak = model.pending_idle_seconds
    button(dialog, "resumeButton").click()

    assert model.state is TimerState.RUNNING
    assert model.idle_seconds == peak
    assert timer_controller.is_ticking is True
    assert not dialog.isVisible()


def test_discard_runs_and_drops_idle(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    button(dialog, "discardButton").click()

    assert model.state is TimerState.RUNNING
    assert model.idle_seconds == 0
    assert not dialog.isVisible()


def test_stop_while_auto_paused_keeps_idle_and_hides_dialog(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    button(widget, "stopButton").click()

    assert model.state is TimerState.IDLE
    assert not dialog.isVisible()
    assert idle_controller.is_polling is False

    detector.reading = 0
    idle_controller.poll()
    assert not dialog.isVisible()


def test_widget_resume_while_auto_paused_hides_dialog(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    peak = model.pending_idle_seconds
    button(widget, "startPauseButton").click()

    assert model.state is TimerState.RUNNING
    assert model.idle_seconds == peak
    assert not dialog.isVisible()


def test_unavailable_detector_does_not_auto_pause(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    model: TimerModel,
    clock: FakeClock,
) -> None:
    start(widget)
    clock.advance(WORK + THRESHOLD)
    detector.reading = None
    idle_controller.poll()
    assert model.state is TimerState.RUNNING
    assert not dialog.isVisible()


def test_poll_timer_only_in_running_and_auto_paused(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    clock: FakeClock,
) -> None:
    assert idle_controller.is_polling is False
    start(widget)
    assert idle_controller.is_polling is True
    button(widget, "startPauseButton").click()
    assert idle_controller.is_polling is False
    button(widget, "startPauseButton").click()
    assert idle_controller.is_polling is True

    clock.advance(WORK + THRESHOLD)
    detector.reading = THRESHOLD
    idle_controller.poll()
    assert idle_controller.is_polling is True

    button(dialog, "keepButton").click()
    assert idle_controller.is_polling is False


def test_real_qtimer_triggers_auto_pause(
    model: TimerModel,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    clock: FakeClock,
) -> None:
    timer = TimerController(model, widget, interval_ms=20)
    idle = IdleController(
        model,
        widget,
        dialog,
        detector,
        threshold=lambda: THRESHOLD,
        timer_controller=timer,
        interval_ms=20,
    )
    try:
        start(widget)
        clock.advance(WORK + THRESHOLD)
        detector.reading = THRESHOLD
        QTest.qWait(1500)
        assert model.state is TimerState.AUTO_PAUSED
        assert dialog.isVisible()
    finally:
        idle.deleteLater()
        timer.deleteLater()
