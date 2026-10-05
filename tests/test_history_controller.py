import logging
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from PySide6.QtCore import QDate, QPoint
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QLabel,
    QPushButton,
    QTableWidget,
)

from furniture_timer import db
from furniture_timer.formatting import format_datetime, format_hms
from furniture_timer.i18n import t
from furniture_timer.main import _persist_session
from furniture_timer.session_csv import CSV_COLUMNS
from furniture_timer.timer_model import TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.history_controller import (
    GetSavePath,
    HistoryController,
    sort_sessions_by_project,
)
from furniture_timer.ui.history_dialog import HistoryDialog
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget

WALL_START = 1_700_000_000.0
RATE = 20.0


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def wall(self) -> float:
        return WALL_START + self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = db.connect(tmp_path / "db.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def settings_dialog(widget: TimerWidget) -> Iterator[SettingsDialog]:
    d = SettingsDialog(widget)
    yield d
    d.hide()
    d.close()
    d.deleteLater()


@pytest.fixture
def dialog(widget: TimerWidget) -> Iterator[HistoryDialog]:
    d = HistoryDialog(widget)
    yield d
    d.hide()
    d.close()
    d.deleteLater()


@pytest.fixture
def model(clock: FakeClock) -> TimerModel:
    return TimerModel(clock=clock, wall_clock=clock.wall)


@pytest.fixture
def timer_controller(
    model: TimerModel, widget: TimerWidget, conn: sqlite3.Connection
) -> Iterator[TimerController]:
    c = TimerController(
        model,
        widget,
        hourly_rate=lambda: RATE,
        persist_session=lambda result, snap, cost: _persist_session(
            conn, result, snap, cost
        ),
    )
    yield c
    c.deleteLater()


def _make_history(
    conn: sqlite3.Connection,
    widget: TimerWidget,
    settings_dialog: SettingsDialog,
    dialog: HistoryDialog,
    timer_controller: TimerController,
    get_save_path: GetSavePath,
) -> HistoryController:
    return HistoryController(
        conn,
        widget,
        settings_dialog,
        dialog,
        timer_controller,
        get_save_path=get_save_path,
    )


@pytest.fixture
def controller(
    conn: sqlite3.Connection,
    widget: TimerWidget,
    settings_dialog: SettingsDialog,
    dialog: HistoryDialog,
    timer_controller: TimerController,
    tmp_path: Path,
) -> Iterator[HistoryController]:
    c = _make_history(
        conn,
        widget,
        settings_dialog,
        dialog,
        timer_controller,
        lambda: tmp_path / "sessions.csv",
    )
    yield c
    c.deleteLater()


def _button(parent: SettingsDialog | HistoryDialog | TimerWidget, name: str) -> QPushButton:
    button = parent.findChild(QPushButton, name)
    assert button is not None, name
    return button


def _table(dialog: HistoryDialog) -> QTableWidget:
    table = dialog.findChild(QTableWidget, "historyTable")
    assert table is not None
    return table


def _empty(dialog: HistoryDialog) -> QLabel:
    label = dialog.findChild(QLabel, "emptyLabel")
    assert label is not None
    return label


def _error(dialog: HistoryDialog) -> QLabel:
    label = dialog.findChild(QLabel, "errorLabel")
    assert label is not None
    return label


def test_settings_history_hides_settings_and_shows_empty(
    controller: HistoryController,
    settings_dialog: SettingsDialog,
    dialog: HistoryDialog,
) -> None:
    settings_dialog.show()
    _button(settings_dialog, "historyButton").click()
    assert not settings_dialog.isVisible()
    assert dialog.isVisible()
    assert _empty(dialog).isVisible()
    assert _table(dialog).isHidden()
    assert not _button(dialog, "exportButton").isEnabled()


def test_open_lists_recent_sessions(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    db.insert_session(conn, 100, 200, 60, 5, 30.0, 0.5, "a")
    db.insert_session(conn, 300, 400, 120, 0, 20.0, 10.0, "b")
    controller.open()
    table = _table(dialog)
    assert dialog.isVisible()
    assert table.isVisible()
    assert _empty(dialog).isHidden()
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == format_datetime(300)
    assert table.item(0, 1).text() == format_hms(120)
    assert table.item(0, 2).text() == "10.00"
    assert table.item(0, 3).text() == ""
    assert table.item(0, 4).text() == ""
    assert table.item(0, 5).text() == ""
    assert table.item(1, 0).text() == format_datetime(100)
    assert table.item(1, 1).text() == format_hms(60)
    assert table.item(1, 2).text() == "0.50"
    assert _button(dialog, "exportButton").isEnabled()


def test_stop_refreshes_visible_history(
    controller: HistoryController,
    dialog: HistoryDialog,
    widget: TimerWidget,
    clock: FakeClock,
    model: TimerModel,
) -> None:
    controller.open()
    assert _empty(dialog).isVisible()
    _button(widget, "startPauseButton").click()
    clock.advance(1800)
    _button(widget, "stopButton").click()
    table = _table(dialog)
    assert model.state is TimerState.IDLE
    assert table.isVisible()
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == format_datetime(int(WALL_START))
    assert table.item(0, 1).text() == format_hms(1800)
    assert table.item(0, 2).text() == "10.00"


def test_open_shows_project_and_client(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    db.insert_session(
        conn,
        100,
        160,
        60,
        0,
        20.0,
        0.5,
        project_number="12",
        project_name="Kitchen",
        client_name="Ivan",
    )
    controller.open()
    table = _table(dialog)
    assert table.item(0, 3).text() == "12"
    assert table.item(0, 4).text() == "Kitchen"
    assert table.item(0, 5).text() == "Ivan"


def test_clear_removes_sessions_and_shows_empty(
    controller: HistoryController,
    dialog: HistoryDialog,
    widget: TimerWidget,
    conn: sqlite3.Connection,
) -> None:
    db.insert_session(
        conn, 100, 160, 60, 0, 20.0, 0.5, project_number="12", client_name="Ivan"
    )
    with conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('hourly_rate', '20')")
    widget.set_job_suggestions([("12", "Kitchen")], ["Ivan"])
    controller.open()
    assert _button(dialog, "clearButton").isEnabled()
    _button(dialog, "clearButton").click()
    assert db.list_recent_sessions(conn) == []
    assert conn.execute("SELECT value FROM settings WHERE key = 'hourly_rate'").fetchone() == (
        "20",
    )
    assert _empty(dialog).isVisible()
    assert _table(dialog).isHidden()
    assert not _button(dialog, "clearButton").isEnabled()
    assert not _button(dialog, "exportButton").isEnabled()
    number = widget.findChild(QComboBox, "projectNumberCombo")
    assert number is not None
    assert number.count() == 0


def _session(row_id: int, number: str) -> db.SessionRow:
    return db.SessionRow(row_id, row_id, row_id, 1, 0, 0.0, 1.0, "", number, "", "")


def test_sort_project_numbers_numeric_blank_and_direction() -> None:
    rows = [_session(1, "12"), _session(2, ""), _session(3, "7"), _session(4, "7")]
    ascending = sort_sessions_by_project(rows, descending=False)
    assert [row.id for row in ascending] == [4, 3, 1, 2]
    descending = sort_sessions_by_project(rows, descending=True)
    assert [row.id for row in descending] == [1, 4, 3, 2]


def test_header_sort_reorders_visible_rows(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    db.insert_session(conn, 1, 2, 1, 0, 0.0, 0.0, project_number="12")
    db.insert_session(conn, 3, 4, 1, 0, 0.0, 0.0, project_number="")
    db.insert_session(conn, 5, 6, 1, 0, 0.0, 0.0, project_number="7")
    db.insert_session(conn, 7, 8, 1, 0, 0.0, 0.0, project_number="7")
    controller.open()
    header = _table(dialog).horizontalHeader()
    header.sectionClicked.emit(3)
    assert [_table(dialog).item(row, 3).text() for row in range(4)] == ["7", "7", "12", ""]
    header.sectionClicked.emit(3)
    assert [_table(dialog).item(row, 3).text() for row in range(4)] == ["12", "7", "7", ""]


def test_summary_follows_project_and_period(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    inside = datetime.now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    outside = inside.replace(year=inside.year - 1)
    db.insert_session(
        conn, int(inside.timestamp()), int(inside.timestamp()) + 10, 3600, 0, 0.0, 10.0, project_number="7"
    )
    db.insert_session(
        conn, int(outside.timestamp()), int(outside.timestamp()) + 10, 100, 0, 0.0, 99.0, project_number="7"
    )
    db.insert_session(
        conn, int(inside.timestamp()), int(inside.timestamp()) + 10, 50, 0, 0.0, 5.0, project_number="12"
    )
    controller.open()
    summary = dialog.findChild(QLabel, "summaryLabel")
    project = dialog.findChild(QComboBox, "summaryProject")
    assert summary is not None and project is not None
    assert summary.text() == t("history.summary.pick")
    project.setCurrentIndex(project.findData("7"))
    assert summary.text() == t("history.summary.total", time=format_hms(3600), cost=10.0)
    past = QDate(outside.year, outside.month, outside.day)
    period_from = dialog.findChild(QDateEdit, "periodFrom")
    period_to = dialog.findChild(QDateEdit, "periodTo")
    assert period_from is not None and period_to is not None
    period_from.setDate(past)
    period_to.setDate(past)
    assert summary.text() == t("history.summary.total", time=format_hms(100), cost=99.0)


def test_export_writes_chosen_path(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection, tmp_path: Path
) -> None:
    db.insert_session(conn, 100, 160, 60, 0, 20.0, 0.5)
    controller.open()
    _button(dialog, "exportButton").click()
    path = tmp_path / "sessions.csv"
    assert path.is_file()
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == ",".join(CSV_COLUMNS)
    assert len(lines) == 2
    assert lines[1].startswith("1,100,160,60,")


def test_export_cancel_does_not_create_file(
    conn: sqlite3.Connection,
    widget: TimerWidget,
    settings_dialog: SettingsDialog,
    dialog: HistoryDialog,
    timer_controller: TimerController,
    tmp_path: Path,
) -> None:
    db.insert_session(conn, 1, 2, 1, 0, 0.0, 0.0)
    target = tmp_path / "sessions.csv"
    controller = _make_history(
        conn, widget, settings_dialog, dialog, timer_controller, lambda: None
    )
    try:
        controller.open()
        _button(dialog, "exportButton").click()
        assert not target.exists()
        assert dialog.isVisible()
        assert _error(dialog).isHidden()
    finally:
        controller.deleteLater()


def test_export_write_failure_logs_and_keeps_panel(
    conn: sqlite3.Connection,
    widget: TimerWidget,
    settings_dialog: SettingsDialog,
    dialog: HistoryDialog,
    timer_controller: TimerController,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db.insert_session(conn, 1, 2, 1, 0, 0.0, 0.0)
    controller = _make_history(
        conn, widget, settings_dialog, dialog, timer_controller, lambda: tmp_path
    )
    try:
        controller.open()
        with caplog.at_level(logging.ERROR):
            _button(dialog, "exportButton").click()
        assert dialog.isVisible()
        assert _error(dialog).isVisible()
        assert _error(dialog).text() == t("history.error.write")
        assert "Failed to write session CSV" in caplog.text
    finally:
        controller.deleteLater()


def test_close_hides_history(
    controller: HistoryController, dialog: HistoryDialog, settings_dialog: SettingsDialog
) -> None:
    controller.open()
    _button(dialog, "closeButton").click()
    assert not dialog.isVisible()
    assert not settings_dialog.isVisible()


def test_open_history_follows_widget_move(
    controller: HistoryController, dialog: HistoryDialog, widget: TimerWidget
) -> None:
    widget.move(100, 100)
    controller.open()
    before = dialog.pos()
    delta = QPoint(40, 25)
    widget.move(widget.pos() + delta)
    assert dialog.isVisible()
    assert dialog.pos() == before + delta


def test_hidden_history_does_not_follow(
    controller: HistoryController, dialog: HistoryDialog, widget: TimerWidget
) -> None:
    widget.move(100, 100)
    controller.open()
    _button(dialog, "closeButton").click()
    parked = dialog.pos()
    widget.move(widget.pos() + QPoint(40, 25))
    assert not dialog.isVisible()
    assert dialog.pos() == parked
