"""Open the settings panel and persist validated values."""

import logging

from PySide6.QtCore import QObject, Signal

from furniture_timer.i18n import set_language, t
from furniture_timer.settings import (
    Settings,
    parse_currency,
    parse_hourly_rate,
    parse_idle_threshold,
    parse_language,
)
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)


class SettingsController(QObject):
    language_changed = Signal()

    def __init__(
        self,
        settings: Settings,
        widget: TimerWidget,
        dialog: SettingsDialog,
        timer_controller: TimerController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._widget = widget
        self._dialog = dialog
        self._timer_controller = timer_controller

        widget.settings_clicked.connect(self.open)
        widget.moved.connect(self._follow)
        dialog.save_clicked.connect(self._on_save)
        dialog.cancel_clicked.connect(self._on_cancel)

    def open(self) -> None:
        if not self._dialog.isVisible():
            self._dialog.set_values(
                self._settings.hourly_rate,
                self._settings.currency,
                self._settings.idle_threshold_sec,
                self._settings.language,
            )
            self._dialog.clear_error()
        self._dialog.place_near(self._widget.frameGeometry())
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _follow(self) -> None:
        if self._dialog.isVisible():
            self._dialog.place_near(self._widget.frameGeometry())

    def _on_save(self) -> None:
        raw_rate, raw_currency, raw_idle, raw_language = self._dialog.values()
        try:
            rate = parse_hourly_rate(raw_rate)
        except (TypeError, ValueError):
            self._dialog.show_error(t("settings.error.rate"))
            return
        try:
            currency = parse_currency(raw_currency)
        except (TypeError, ValueError):
            self._dialog.show_error(t("settings.error.currency"))
            return
        try:
            idle = parse_idle_threshold(raw_idle)
        except (TypeError, ValueError):
            self._dialog.show_error(t("settings.error.idle_threshold"))
            return
        try:
            language = parse_language(raw_language)
        except (TypeError, ValueError):
            self._dialog.show_error(t("settings.error.language"))
            return
        self._settings.hourly_rate = rate
        self._settings.currency = currency
        self._settings.idle_threshold_sec = idle
        self._settings.language = language
        self._settings.save()
        set_language(language)
        log.info(
            "Settings saved: rate=%s currency=%s idle_threshold=%ss language=%s",
            rate,
            currency,
            idle,
            language,
        )
        self._timer_controller.refresh()
        self.language_changed.emit()
        self._dialog.hide()

    def _on_cancel(self) -> None:
        self._dialog.hide()
