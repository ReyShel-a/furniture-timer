"""System tray icon: Show, Start/Pause, Quit."""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from furniture_timer.i18n import t
from furniture_timer.timer_model import TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.theme import ACCENT
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)

ICON_SIZE = 16

_TOGGLE_KEYS: dict[TimerState, str] = {
    TimerState.IDLE: "btn.start",
    TimerState.RUNNING: "btn.pause",
    TimerState.PAUSED: "btn.resume",
    TimerState.AUTO_PAUSED: "btn.resume",
}


class TrayController(QObject):
    quit_requested = Signal()

    def __init__(
        self,
        widget: TimerWidget,
        timer_controller: TimerController,
        available: bool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._widget = widget
        self._timer = timer_controller
        self._active = (
            QSystemTrayIcon.isSystemTrayAvailable() if available is None else available
        )
        self._icon: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None
        self._show_action: QAction | None = None
        self._toggle_action: QAction | None = None
        self._quit_action: QAction | None = None

        if not self._active:
            log.warning("System tray is not available; close will quit the app")
            return

        self._icon = QSystemTrayIcon(_tray_icon(), self)
        self._icon.setToolTip(t("app.title"))
        self._menu = QMenu()
        self._show_action = self._menu.addAction(t("tray.action.show"))
        self._toggle_action = self._menu.addAction(t(_TOGGLE_KEYS[timer_controller.state]))
        self._quit_action = self._menu.addAction(t("tray.action.quit"))
        self._show_action.triggered.connect(self.show_widget)
        self._toggle_action.triggered.connect(self._on_toggle)
        self._quit_action.triggered.connect(self._request_quit)
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        self._timer.state_changed.connect(self._sync_toggle_label)
        self.destroyed.connect(self._icon.hide)
        self.destroyed.connect(self._menu.deleteLater)
        self._icon.show()

    @property
    def active(self) -> bool:
        return self._active

    @property
    def icon(self) -> QSystemTrayIcon | None:
        return self._icon

    @property
    def show_action(self) -> QAction | None:
        return self._show_action

    @property
    def toggle_action(self) -> QAction | None:
        return self._toggle_action

    @property
    def quit_action(self) -> QAction | None:
        return self._quit_action

    def hide_widget(self) -> None:
        self._widget.hide()

    def show_widget(self) -> None:
        self._widget.show()
        self._widget.raise_()
        self._widget.activateWindow()

    def _on_toggle(self) -> None:
        self._timer.toggle_start_pause()

    def _request_quit(self) -> None:
        self.quit_requested.emit()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_widget()

    def retranslate(self) -> None:
        if self._icon is None or self._show_action is None or self._quit_action is None:
            return
        self._icon.setToolTip(t("app.title"))
        self._show_action.setText(t("tray.action.show"))
        self._quit_action.setText(t("tray.action.quit"))
        self._sync_toggle_label()

    def _sync_toggle_label(self) -> None:
        if self._toggle_action is None:
            return
        self._toggle_action.setText(t(_TOGGLE_KEYS[self._timer.state]))


def _tray_icon() -> QIcon:
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(QColor(ACCENT))
    return QIcon(pixmap)
