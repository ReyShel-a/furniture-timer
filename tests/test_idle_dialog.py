from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from furniture_timer.formatting import format_hms
from furniture_timer.i18n import t
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.widget import TimerWidget
from tests.idle_support import THRESHOLD, button, message


def test_dialog_does_not_steal_focus(dialog: IdleDialog, widget: TimerWidget) -> None:
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    dialog.place_near(widget.frameGeometry())
    dialog.show_alert(format_hms(THRESHOLD))
    assert QApplication.activeWindow() is not dialog


def test_dialog_three_buttons_and_alert_text(dialog: IdleDialog) -> None:
    duration = format_hms(THRESHOLD)
    dialog.show_alert(duration)
    assert message(dialog) == t("idle.dialog.message", duration=duration)
    assert button(dialog, "keepButton").text() == t("idle.btn.keep")
    assert button(dialog, "discardButton").text() == t("idle.btn.discard")
    assert button(dialog, "resumeButton").text() == t("idle.btn.resume")
    dialog.show_prompt(duration)
    assert dialog.is_prompt
    assert message(dialog) == t("idle.prompt.message", duration=duration)