import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

from furniture_timer import db
from furniture_timer.i18n import t
from furniture_timer.settings import Settings
from furniture_timer.timer_model import TimerModel
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.settings_controller import SettingsController
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = db.connect(tmp_path / "db.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def settings(conn: sqlite3.Connection) -> Settings:
    return Settings(conn)


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


@pytest.fixture
def timer_controller(widget: TimerWidget, settings: Settings) -> Iterator[TimerController]:
    c = TimerController(
        TimerModel(),
        widget,
        hourly_rate=lambda: settings.hourly_rate,
        currency=lambda: settings.currency,
    )
    yield c
    c.deleteLater()


@pytest.fixture
def controller(
    settings: Settings,
    widget: TimerWidget,
    dialog: SettingsDialog,
    timer_controller: TimerController,
) -> Iterator[SettingsController]:
    c = SettingsController(settings, widget, dialog, timer_controller)
    yield c
    c.deleteLater()


def _button(dialog: SettingsDialog, name: str) -> QPushButton:
    button = dialog.findChild(QPushButton, name)
    assert button is not None, name
    return button


def _edit(dialog: SettingsDialog, name: str) -> QLineEdit:
    edit = dialog.findChild(QLineEdit, name)
    assert edit is not None, name
    return edit


def _error(dialog: SettingsDialog) -> QLabel:
    label = dialog.findChild(QLabel, "errorLabel")
    assert label is not None
    return label


def _price(widget: TimerWidget) -> str:
    label = widget.findChild(QLabel, "priceLabel")
    assert label is not None
    return label.text()


def _fill(dialog: SettingsDialog, rate: str, currency: str, idle: str) -> None:
    _edit(dialog, "rateEdit").setText(rate)
    _edit(dialog, "currencyEdit").setText(currency)
    _edit(dialog, "idleEdit").setText(idle)


def test_open_loads_current_settings(
    controller: SettingsController, dialog: SettingsDialog, settings: Settings
) -> None:
    settings.hourly_rate = 8.5
    settings.currency = "$"
    settings.idle_threshold_sec = 90
    controller.open()
    assert dialog.isVisible()
    assert dialog.values() == ("8.5", "$", "90")


def test_save_persists_valid_values(
    controller: SettingsController,
    dialog: SettingsDialog,
    settings: Settings,
    conn: sqlite3.Connection,
) -> None:
    controller.open()
    _fill(dialog, "42.5", "EUR", "120")
    _button(dialog, "saveButton").click()

    assert not dialog.isVisible()
    assert settings.hourly_rate == 42.5
    assert settings.currency == "EUR"
    assert settings.idle_threshold_sec == 120
    reloaded = Settings(conn)
    assert reloaded.hourly_rate == 42.5
    assert reloaded.currency == "EUR"
    assert reloaded.idle_threshold_sec == 120


def test_save_refreshes_price_label(
    controller: SettingsController,
    dialog: SettingsDialog,
    widget: TimerWidget,
) -> None:
    controller.open()
    _fill(dialog, "12.5", "$", "300")
    _button(dialog, "saveButton").click()
    assert _price(widget) == "12.50 $/h  ·  0.00 $"


@pytest.mark.parametrize(
    ("rate", "currency", "idle", "error_key"),
    [
        ("abc", "$", "300", "settings.error.rate"),
        ("-1", "$", "300", "settings.error.rate"),
        ("10", "   ", "300", "settings.error.currency"),
        ("10", "$", "0", "settings.error.idle_threshold"),
        ("10", "$", "1.5", "settings.error.idle_threshold"),
    ],
)
def test_invalid_save_shows_error_and_keeps_db(
    controller: SettingsController,
    dialog: SettingsDialog,
    settings: Settings,
    conn: sqlite3.Connection,
    rate: str,
    currency: str,
    idle: str,
    error_key: str,
) -> None:
    controller.open()
    _fill(dialog, rate, currency, idle)
    _button(dialog, "saveButton").click()

    assert dialog.isVisible()
    assert _error(dialog).isVisible()
    assert _error(dialog).text() == t(error_key)
    assert settings.hourly_rate == 0.0
    assert settings.currency == "₽"
    assert settings.idle_threshold_sec == 300
    assert dict(conn.execute("SELECT key, value FROM settings")) == {}


def test_cancel_does_not_persist(
    controller: SettingsController,
    dialog: SettingsDialog,
    settings: Settings,
    conn: sqlite3.Connection,
) -> None:
    controller.open()
    _fill(dialog, "99", "USD", "10")
    _button(dialog, "cancelButton").click()

    assert not dialog.isVisible()
    assert settings.hourly_rate == 0.0
    assert settings.currency == "₽"
    assert settings.idle_threshold_sec == 300
    assert dict(conn.execute("SELECT key, value FROM settings")) == {}


def test_reopen_while_visible_keeps_unsaved_edits(
    controller: SettingsController, dialog: SettingsDialog
) -> None:
    controller.open()
    _fill(dialog, "7", "£", "45")
    controller.open()
    assert dialog.values() == ("7", "£", "45")


def test_reopen_after_cancel_reloads_saved_values(
    controller: SettingsController, dialog: SettingsDialog, settings: Settings
) -> None:
    controller.open()
    _fill(dialog, "7", "£", "45")
    _button(dialog, "cancelButton").click()
    controller.open()
    assert dialog.values() == (
        str(settings.hourly_rate),
        settings.currency,
        str(settings.idle_threshold_sec),
    )


def test_open_settings_follow_widget_move(
    controller: SettingsController, dialog: SettingsDialog, widget: TimerWidget
) -> None:
    widget.move(100, 100)
    controller.open()
    before = dialog.pos()
    delta = QPoint(40, 25)
    widget.move(widget.pos() + delta)
    assert dialog.isVisible()
    assert dialog.pos() == before + delta


def test_hidden_settings_do_not_follow(
    controller: SettingsController, dialog: SettingsDialog, widget: TimerWidget
) -> None:
    widget.move(100, 100)
    controller.open()
    _button(dialog, "cancelButton").click()
    parked = dialog.pos()
    widget.move(widget.pos() + QPoint(40, 25))
    assert not dialog.isVisible()
    assert dialog.pos() == parked
