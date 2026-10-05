"""Load recent sessions into the history panel and export CSV."""

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog

from furniture_timer import db
from furniture_timer.formatting import format_datetime, format_hms
from furniture_timer.i18n import t
from furniture_timer.session_csv import write_sessions_csv
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.history_dialog import HistoryDialog
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)

GetSavePath = Callable[[], Path | None]


class HistoryController(QObject):
    def __init__(
        self,
        conn: sqlite3.Connection,
        widget: TimerWidget,
        settings_dialog: SettingsDialog,
        dialog: HistoryDialog,
        timer_controller: TimerController,
        get_save_path: GetSavePath | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._widget = widget
        self._settings_dialog = settings_dialog
        self._dialog = dialog
        self._rows: list[db.SessionRow] = []
        self._get_save_path = get_save_path or self._ask_save_path

        settings_dialog.history_clicked.connect(self.open)
        widget.moved.connect(self._follow)
        dialog.export_clicked.connect(self._on_export)
        dialog.close_clicked.connect(self._on_close)
        timer_controller.state_changed.connect(self._on_state_changed)

    def open(self) -> None:
        self._settings_dialog.hide()
        self._reload()
        self._dialog.place_near(self._widget.frameGeometry())
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _reload(self) -> None:
        self._dialog.clear_error()
        try:
            self._rows = db.list_recent_sessions(self._conn)
        except Exception:
            log.exception("Failed to load session history")
            self._rows = []
            self._dialog.set_rows([])
            self._dialog.show_empty(True)
            self._dialog.set_export_enabled(False)
            return
        if not self._rows:
            self._dialog.set_rows([])
            self._dialog.show_empty(True)
            self._dialog.set_export_enabled(False)
            return
        display = [
            (
                format_datetime(row.start_ts),
                format_hms(row.active_seconds),
                f"{row.cost:.2f}",
            )
            for row in self._rows
        ]
        self._dialog.set_rows(display)
        self._dialog.show_empty(False)
        self._dialog.set_export_enabled(True)

    def _follow(self) -> None:
        if self._dialog.isVisible():
            self._dialog.place_near(self._widget.frameGeometry())

    def _on_state_changed(self) -> None:
        if self._dialog.isVisible():
            self._reload()
            self._dialog.place_near(self._widget.frameGeometry())

    def _on_export(self) -> None:
        if not self._rows:
            return
        path = self._get_save_path()
        if path is None:
            return
        try:
            write_sessions_csv(path, self._rows)
        except Exception:
            log.exception("Failed to write session CSV")
            self._dialog.show_error(t("history.error.write"))
            return
        self._dialog.clear_error()
        log.info("Exported %d sessions to %s", len(self._rows), path)

    def _on_close(self) -> None:
        self._dialog.hide()

    def _ask_save_path(self) -> Path | None:
        chosen, _filter = QFileDialog.getSaveFileName(
            self._dialog,
            t("history.export.title"),
            "sessions.csv",
            t("history.export.filter"),
        )
        if not chosen:
            return None
        return Path(chosen)
