"""Load sessions for a period into the history panel and export a cost report."""

import logging
import sqlite3
from collections.abc import Callable, Sequence
from functools import cmp_to_key
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog

from furniture_timer import db
from furniture_timer.formatting import format_datetime, format_hms
from furniture_timer.i18n import t
from furniture_timer.session_csv import (
    BLANK_PROJECT,
    group_sessions_by_project,
    write_selection_report_csv,
)
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.history_dialog import PROJECT_COLUMN, START_COLUMN, HistoryDialog
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
        self._date_sort_desc: bool | None = None
        self._project_sort_desc: bool | None = None
        self._get_save_path = get_save_path or self._ask_save_path

        settings_dialog.history_clicked.connect(self.open)
        widget.moved.connect(self._follow)
        dialog.export_clicked.connect(self._on_export)
        dialog.delete_clicked.connect(self._on_delete)
        dialog.clear_clicked.connect(self._on_clear)
        dialog.close_clicked.connect(self._on_close)
        dialog.sort_clicked.connect(self._on_sort)
        dialog.summary_changed.connect(self._refresh_summary)
        dialog.period_changed.connect(self._reload)
        dialog.selection_changed.connect(self._refresh_selection)
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
            start_ts, end_ts = self._dialog.period_bounds()
            self._rows = db.list_sessions_between(self._conn, start_ts, end_ts)
            projects = db.list_known_projects(self._conn)
        except Exception:
            log.exception("Failed to load session history")
            self._rows = []
            self._dialog.set_project_choices([])
            self._show_rows()
            self._refresh_summary()
            return
        self._dialog.set_project_choices(project.number for project in projects)
        self._show_rows()
        self._refresh_summary()

    def _show_rows(self) -> None:
        visible = self._visible_rows()
        self._dialog.set_rows(
            [
                (
                    row.id,
                    format_datetime(row.start_ts),
                    format_hms(row.active_seconds),
                    f"{row.cost:.2f}",
                    row.project_number,
                    row.project_name,
                    row.client_name,
                )
                for row in visible
            ]
        )
        if not visible:
            self._dialog.show_empty(True)
            self._dialog.set_clear_enabled(False)
        else:
            self._dialog.show_empty(False)
            self._dialog.set_clear_enabled(True)
        self._refresh_selection()

    def _visible_rows(self) -> list[db.SessionRow]:
        if self._date_sort_desc is not None:
            return sort_sessions_by_start(self._rows, descending=self._date_sort_desc)
        if self._project_sort_desc is not None:
            return sort_sessions_by_project(self._rows, descending=self._project_sort_desc)
        return self._rows

    def _selected_rows(self) -> list[db.SessionRow]:
        chosen = set(self._dialog.checked_ids())
        return [row for row in self._visible_rows() if row.id in chosen]

    def _on_sort(self, column: int) -> None:
        if column == START_COLUMN:
            self._project_sort_desc = None
            if self._date_sort_desc is None or self._date_sort_desc:
                self._date_sort_desc = False
            else:
                self._date_sort_desc = True
        elif column == PROJECT_COLUMN:
            self._date_sort_desc = None
            if self._project_sort_desc is None or self._project_sort_desc:
                self._project_sort_desc = False
            else:
                self._project_sort_desc = True
        else:
            return
        self._show_rows()

    def _refresh_summary(self) -> None:
        number = self._dialog.selected_project()
        if not number:
            self._dialog.show_summary(t("history.summary.pick"))
            return
        try:
            start_ts, end_ts = self._dialog.period_bounds()
            active_seconds, cost = db.summarize_project(self._conn, number, start_ts, end_ts)
        except Exception:
            log.exception("Failed to summarize project")
            self._dialog.show_error(t("history.error.summary"))
            return
        self._dialog.clear_error()
        self._dialog.show_summary(
            t("history.summary.total", time=format_hms(active_seconds), cost=cost)
        )

    def _refresh_selection(self) -> None:
        selected = self._selected_rows()
        self._dialog.set_export_enabled(bool(selected))
        self._dialog.set_delete_enabled(bool(selected))
        if not selected:
            self._dialog.show_selection("")
            return
        groups = group_sessions_by_project(selected)
        lines = [
            t(
                "history.selection.total",
                count=len(selected),
                time=format_hms(sum(row.active_seconds for row in selected)),
                cost=sum(row.cost for row in selected),
            )
        ]
        for group in groups:
            lines.append(
                t(
                    "history.selection.project",
                    number=group.number or BLANK_PROJECT,
                    name=group.name,
                    time=format_hms(group.active_seconds),
                    cost=group.cost,
                )
            )
        self._dialog.show_selection("\n".join(lines))

    def _follow(self) -> None:
        if self._dialog.isVisible():
            self._dialog.place_near(self._widget.frameGeometry())

    def _on_state_changed(self) -> None:
        if self._dialog.isVisible():
            self._reload()
            self._dialog.place_near(self._widget.frameGeometry())

    def _on_export(self) -> None:
        selected = self._selected_rows()
        if not selected:
            return
        path = self._get_save_path()
        if path is None:
            return
        try:
            write_selection_report_csv(path, selected)
        except Exception:
            log.exception("Failed to write session CSV")
            self._dialog.show_error(t("history.error.write"))
            return
        self._dialog.clear_error()
        log.info("Exported %d sessions to %s", len(selected), path)

    def _on_delete(self) -> None:
        ids = self._dialog.checked_ids()
        if not ids:
            return
        try:
            db.delete_sessions(self._conn, ids)
        except Exception:
            log.exception("Failed to delete sessions")
            self._dialog.show_error(t("history.error.delete"))
            return
        self._load_suggestions()
        self._reload()
        log.info("Deleted %d sessions", len(ids))

    def _on_clear(self) -> None:
        try:
            db.clear_sessions(self._conn)
        except Exception:
            log.exception("Failed to clear session history")
            self._dialog.show_error(t("history.error.clear"))
            return
        self._load_suggestions()
        self._reload()
        log.info("Cleared session history")

    def _load_suggestions(self) -> None:
        try:
            self._widget.set_job_suggestions(
                db.list_known_projects(self._conn),
                db.list_known_clients(self._conn),
            )
        except Exception:
            log.exception("Failed to load project suggestions")

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


def sort_sessions_by_start(
    rows: Sequence[db.SessionRow], descending: bool = False
) -> list[db.SessionRow]:
    """Sort by start time. Equal times keep the newer id first."""

    def key(row: db.SessionRow) -> tuple[int, int]:
        start = -row.start_ts if descending else row.start_ts
        return (start, -row.id)

    return sorted(rows, key=key)


def sort_sessions_by_project(
    rows: Sequence[db.SessionRow], descending: bool = False
) -> list[db.SessionRow]:
    """Sort by project number. Blank numbers stay last; equal numbers keep the newer id first."""

    def compare(left: db.SessionRow, right: db.SessionRow) -> int:
        left_number = left.project_number.strip()
        right_number = right.project_number.strip()
        if not left_number or not right_number:
            if left_number == right_number:
                return _newer_first(left, right)
            return -1 if left_number else 1
        order = _number_order(left_number, right_number)
        if descending:
            order = -order
        if order == 0:
            return _newer_first(left, right)
        return order

    return sorted(rows, key=cmp_to_key(compare))


def _newer_first(left: db.SessionRow, right: db.SessionRow) -> int:
    if left.id == right.id:
        return 0
    return -1 if left.id > right.id else 1


def _number_order(left: str, right: str) -> int:
    if left.isdigit() and right.isdigit():
        return (int(left) > int(right)) - (int(left) < int(right))
    if left.casefold() == right.casefold():
        return 0
    return 1 if left.casefold() > right.casefold() else -1
