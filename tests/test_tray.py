"""System tray menu: Show, Start/Pause, Quit."""

import logging
from collections.abc import Iterator

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from furniture_timer.i18n import t
from furniture_timer.timer_model import TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.tray_controller import TrayController
from furniture_timer.ui.widget import TimerWidget


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def model() -> TimerModel:
    return TimerModel()


@pytest.fixture
def timer_controller(model: TimerModel, widget: TimerWidget) -> Iterator[TimerController]:
    controller = TimerController(model, widget)
    yield controller
    controller.deleteLater()


@pytest.fixture
def tray(
    widget: TimerWidget, timer_controller: TimerController
) -> Iterator[TrayController]:
    controller = TrayController(widget, timer_controller, available=True)
    yield controller
    icon = controller.icon
    if icon is not None:
        icon.hide()
    controller.deleteLater()


def _action(action: QAction | None) -> QAction:
    assert action is not None
    return action


def test_menu_labels_match_i18n(tray: TrayController) -> None:
    assert tray.active is True
    assert _action(tray.show_action).text() == t("tray.action.show")
    assert _action(tray.toggle_action).text() == t("btn.start")
    assert _action(tray.quit_action).text() == t("tray.action.quit")
    icon = tray.icon
    assert icon is not None
    assert icon.isVisible()
    assert icon.toolTip() == t("app.title")


def test_toggle_updates_label_and_state(
    tray: TrayController, model: TimerModel
) -> None:
    _action(tray.toggle_action).trigger()
    assert model.state is TimerState.RUNNING
    assert _action(tray.toggle_action).text() == t("btn.pause")


def test_show_restores_hidden_widget(tray: TrayController, widget: TimerWidget) -> None:
    tray.hide_widget()
    assert widget.isVisible() is False
    _action(tray.show_action).trigger()
    assert widget.isVisible() is True


def test_tray_click_shows_widget(tray: TrayController, widget: TimerWidget) -> None:
    tray.hide_widget()
    icon = tray.icon
    assert icon is not None
    icon.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
    assert widget.isVisible() is True


def test_quit_requests_exit_without_changing_model(
    tray: TrayController, model: TimerModel
) -> None:
    fired: list[int] = []
    tray.quit_requested.connect(lambda: fired.append(1))
    _action(tray.quit_action).trigger()
    assert fired == [1]
    assert model.state is TimerState.IDLE


def test_unavailable_tray_is_inactive(
    widget: TimerWidget, timer_controller: TimerController, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        controller = TrayController(widget, timer_controller, available=False)
    assert controller.active is False
    assert controller.icon is None
    assert controller.show_action is None
    assert "not available" in caplog.text
    controller.deleteLater()
