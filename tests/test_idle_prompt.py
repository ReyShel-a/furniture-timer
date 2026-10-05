from PySide6.QtWidgets import QApplication

from furniture_timer.ui.idle_controller import IdleController
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.widget import TimerWidget
from tests.idle_support import THRESHOLD, FakeClock, FakeIdleDetector, button, enter_auto_pause, message


def test_resume_prompt_when_hidden_and_user_returned(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    dialog.hide()
    QApplication.processEvents()
    assert not dialog.is_on_screen()

    detector.reading = 0
    idle_controller.poll()

    assert dialog.isVisible()
    assert dialog.is_prompt
    assert message(dialog).startswith("Resume?")
    assert button(dialog, "keepButton").isVisible()
    assert button(dialog, "discardButton").isVisible()
    assert button(dialog, "resumeButton").isVisible()


def test_resume_prompt_when_moved_off_screen(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    dialog.move(-10_000, -10_000)
    QApplication.processEvents()
    assert not dialog.is_on_screen()

    detector.reading = 0
    idle_controller.poll()
    assert dialog.is_prompt
    assert dialog.is_on_screen()


def test_no_prompt_while_alert_is_on_screen(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    detector.reading = 0
    idle_controller.poll()
    assert dialog.isVisible()
    assert not dialog.is_prompt


def test_no_prompt_if_user_has_not_returned(
    idle_controller: IdleController,
    widget: TimerWidget,
    dialog: IdleDialog,
    detector: FakeIdleDetector,
    clock: FakeClock,
) -> None:
    enter_auto_pause(widget, clock, detector, idle_controller)
    dialog.hide()
    detector.reading = THRESHOLD
    idle_controller.poll()
    assert not dialog.isVisible()
    assert not dialog.is_prompt
