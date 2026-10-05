from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

from furniture_timer.i18n import t
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget, WIDGET_WIDTH


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def dialog(widget: TimerWidget) -> Iterator[SettingsDialog]:
    d = SettingsDialog(widget)
    yield d
    d.hide()
    d.close()
    d.deleteLater()


def _button(dialog: SettingsDialog, name: str) -> QPushButton:
    button = dialog.findChild(QPushButton, name)
    assert button is not None, name
    return button


def _edit(dialog: SettingsDialog, name: str) -> QLineEdit:
    edit = dialog.findChild(QLineEdit, name)
    assert edit is not None, name
    return edit


def _label(dialog: SettingsDialog, name: str) -> QLabel:
    label = dialog.findChild(QLabel, name)
    assert label is not None, name
    return label


def test_window_flags(dialog: SettingsDialog) -> None:
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    assert not (flags & Qt.WindowType.WindowDoesNotAcceptFocus)
    assert not dialog.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert dialog.width() == WIDGET_WIDTH


def test_children_and_i18n(dialog: SettingsDialog) -> None:
    assert dialog.objectName() == "SettingsDialog"
    assert dialog.windowTitle() == t("settings.dialog.title")
    assert _label(dialog, "settingsTitle").text() == t("settings.dialog.title")
    assert _label(dialog, "rateLabel").text() == t("settings.field.rate")
    assert _label(dialog, "currencyLabel").text() == t("settings.field.currency")
    assert _label(dialog, "idleLabel").text() == t("settings.field.idle_threshold")
    assert _button(dialog, "saveButton").text() == t("settings.btn.save")
    assert _button(dialog, "cancelButton").text() == t("settings.btn.cancel")
    for name in ("rateEdit", "currencyEdit", "idleEdit"):
        _edit(dialog, name)


def test_set_values_roundtrip(dialog: SettingsDialog) -> None:
    dialog.set_values(12.5, "$", 120)
    assert dialog.values() == ("12.5", "$", "120")


def test_show_and_clear_error(dialog: SettingsDialog) -> None:
    error = _label(dialog, "errorLabel")
    assert error.isHidden()
    dialog.show_error(t("settings.error.rate"))
    assert not error.isHidden()
    assert error.text() == t("settings.error.rate")
    dialog.clear_error()
    assert error.isHidden()
    assert error.text() == ""


def test_save_and_cancel_signals(dialog: SettingsDialog) -> None:
    fired: list[str] = []
    dialog.save_clicked.connect(lambda: fired.append("save"))
    dialog.cancel_clicked.connect(lambda: fired.append("cancel"))
    _button(dialog, "saveButton").click()
    _button(dialog, "cancelButton").click()
    assert fired == ["save", "cancel"]


def test_escape_emits_cancel(dialog: SettingsDialog) -> None:
    fired: list[str] = []
    dialog.cancel_clicked.connect(lambda: fired.append("cancel"))
    dialog.save_clicked.connect(lambda: fired.append("save"))
    dialog.show()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert fired == ["cancel"]


def test_place_near_widget(dialog: SettingsDialog, widget: TimerWidget) -> None:
    dialog.place_near(widget.frameGeometry())
    dialog.show()
    assert dialog.isVisible()
