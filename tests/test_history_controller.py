import logging
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QPushButton,
    QTableWidget,
)

from furniture_timer import db
from furniture_timer.formatting import format_datetime, format_hms, format_money
from furniture_timer.i18n import t
from furniture_timer.main import _persist_session
from furniture_timer.session_csv import BLANK_PROJECT, CSV_COLUMNS, GROUP_COLUMNS
from furniture_timer.timer_model import TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.history_controller import (
    GetSavePath,
    HistoryController,
    sort_sessions_by_project,
    sort_sessions_by_start,
)
from furniture_timer.ui.history_dialog import PROJECT_COLUMN, START_COLUMN, HistoryDialog
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
        save_session=lambda row_id, result, rate, cost, finalized: _persist_session(
            conn, result, rate, cost, row_id=row_id, finalized=finalized
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


def _cover(dialog: HistoryDialog, *timestamps: int) -> None:
    """Widen the calendar period so these unix times are visible."""
    moments = [datetime.fromtimestamp(ts) for ts in timestamps]
    first, last = min(moments), max(moments)
    dialog.set_period(
        QDate(first.year, first.month, first.day),
        QDate(last.year, last.month, last.day),
    )


def _check_row(dialog: HistoryDialog, row: int) -> None:
    item = _table(dialog).item(row, 0)
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked)


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
    db.insert_session(conn, WALL_START, WALL_START + 100, 60, 5, 30.0, 0.5, "a")
    db.insert_session(conn, WALL_START + 200, WALL_START + 300, 120, 0, 20.0, 10.0, "b")
    _cover(dialog, WALL_START, WALL_START + 200)
    controller.open()
    table = _table(dialog)
    assert dialog.isVisible()
    assert table.isVisible()
    assert _empty(dialog).isHidden()
    assert table.rowCount() == 2
    assert table.item(0, 1).text() == format_datetime(WALL_START + 200)
    assert table.item(0, 2).text() == format_hms(120)
    assert table.item(0, 3).text() == "10.00"
    assert table.item(0, 4).text() == ""
    assert table.item(0, 5).text() == ""
    assert table.item(0, 6).text() == ""
    assert table.item(1, 1).text() == format_datetime(WALL_START)
    assert table.item(1, 2).text() == format_hms(60)
    assert table.item(1, 3).text() == "0.50"
    assert not _button(dialog, "exportButton").isEnabled()
    assert not _button(dialog, "deleteButton").isEnabled()
    assert _button(dialog, "clearButton").isEnabled()


def test_stop_refreshes_visible_history(
    controller: HistoryController,
    dialog: HistoryDialog,
    widget: TimerWidget,
    clock: FakeClock,
    model: TimerModel,
) -> None:
    _cover(dialog, int(WALL_START))
    controller.open()
    assert _empty(dialog).isVisible()
    _button(widget, "startPauseButton").click()
    clock.advance(1800)
    _button(widget, "stopButton").click()
    table = _table(dialog)
    assert model.state is TimerState.IDLE
    assert table.isVisible()
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == format_datetime(int(WALL_START))
    assert table.item(0, 2).text() == format_hms(1800)
    assert table.item(0, 3).text() == "10.00"


def test_open_shows_project_and_client(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    db.insert_session(
        conn,
        WALL_START,
        WALL_START + 60,
        60,
        0,
        20.0,
        0.5,
        project_number="12",
        project_name="Kitchen",
        client_name="Ivan",
    )
    _cover(dialog, WALL_START)
    controller.open()
    table = _table(dialog)
    assert table.item(0, 4).text() == "12"
    assert table.item(0, 5).text() == "Kitchen"
    assert table.item(0, 6).text() == "Ivan"


def test_clear_removes_sessions_and_shows_empty(
    controller: HistoryController,
    dialog: HistoryDialog,
    widget: TimerWidget,
    conn: sqlite3.Connection,
) -> None:
    db.insert_session(
        conn, WALL_START, WALL_START + 60, 60, 0, 20.0, 0.5, project_number="12", client_name="Ivan"
    )
    with conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('hourly_rate', '20')")
    widget.set_job_suggestions([("12", "Kitchen")], ["Ivan"])
    _cover(dialog, WALL_START)
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
    db.insert_session(conn, WALL_START, WALL_START + 1, 1, 0, 0.0, 0.0, project_number="12")
    db.insert_session(conn, WALL_START + 2, WALL_START + 3, 1, 0, 0.0, 0.0, project_number="")
    db.insert_session(conn, WALL_START + 4, WALL_START + 5, 1, 0, 0.0, 0.0, project_number="7")
    db.insert_session(conn, WALL_START + 6, WALL_START + 7, 1, 0, 0.0, 0.0, project_number="7")
    _cover(dialog, WALL_START, WALL_START + 6)
    controller.open()
    header = _table(dialog).horizontalHeader()
    header.sectionClicked.emit(PROJECT_COLUMN)
    assert [_table(dialog).item(row, 4).text() for row in range(4)] == ["7", "7", "12", ""]
    header.sectionClicked.emit(PROJECT_COLUMN)
    assert [_table(dialog).item(row, 4).text() for row in range(4)] == ["12", "7", "7", ""]


def test_client_filter_totals_projects_and_period(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    inside = datetime.now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    outside = inside.replace(year=inside.year - 1)
    db.insert_session(
        conn,
        int(inside.timestamp()),
        int(inside.timestamp()) + 10,
        3600,
        0,
        0.0,
        10.0,
        project_number="7",
        project_name="Kitchen",
        client_name="Ivan",
    )
    db.insert_session(
        conn,
        int(inside.timestamp()) + 20,
        int(inside.timestamp()) + 30,
        50,
        0,
        0.0,
        5.0,
        project_number="12",
        project_name="Hall",
        client_name="Ivan",
    )
    db.insert_session(
        conn,
        int(outside.timestamp()),
        int(outside.timestamp()) + 10,
        100,
        0,
        0.0,
        99.0,
        project_number="7",
        project_name="Kitchen",
        client_name="Ivan",
    )
    db.insert_session(
        conn,
        int(inside.timestamp()) + 40,
        int(inside.timestamp()) + 50,
        20,
        0,
        0.0,
        3.0,
        project_number="3",
        project_name="Desk",
        client_name="Anna",
    )
    controller.open()
    cost = dialog.findChild(QLabel, "summaryCost")
    caption = dialog.findChild(QLabel, "summaryCaption")
    time_label = dialog.findChild(QLabel, "summaryTime")
    client = dialog.findChild(QComboBox, "summaryClient")
    project = dialog.findChild(QComboBox, "summaryProject")
    assert cost is not None and caption is not None and time_label is not None
    assert client is not None and project is not None
    assert cost.isHidden()
    assert caption.text() == t("history.summary.pick")
    assert not project.isEnabled()
    assert _table(dialog).rowCount() == 3

    client.setCurrentIndex(client.findData("Ivan"))
    assert project.isEnabled()
    assert project.itemText(0) == t("history.filter.project.all")
    assert "Kitchen" in project.itemText(project.findData("7"))
    assert project.findData("3") < 0
    assert _table(dialog).rowCount() == 2
    assert { _table(dialog).item(row, 6).text() for row in range(2) } == {"Ivan"}
    assert cost.text() == format_money(15.0, "₽")
    assert not cost.isHidden()
    assert time_label.text() == format_hms(3650)
    assert caption.text() == t(
        "history.summary.caption", client="Ivan", period=dialog.period_label()
    )

    project.setCurrentIndex(project.findData("7"))
    assert _table(dialog).rowCount() == 1
    assert _table(dialog).item(0, 4).text() == "7"
    assert cost.text() == format_money(10.0, "₽")
    assert time_label.text() == format_hms(3600)
    assert caption.text() == t(
        "history.summary.caption.project",
        client="Ivan",
        number="7 Kitchen",
        period=dialog.period_label(),
    )

    past = QDate(outside.year, outside.month, outside.day)
    dialog.set_period(past, past)
    assert _table(dialog).rowCount() == 1
    assert cost.text() == format_money(99.0, "₽")
    assert time_label.text() == format_hms(100)


def test_export_writes_chosen_path(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection, tmp_path: Path
) -> None:
    older = int(WALL_START)
    newer = WALL_START + 80
    db.insert_session(conn, older, older + 60, 60, 0, 20.0, 0.5)
    db.insert_session(conn, newer, newer + 20, 10, 0, 20.0, 1.0, project_number="9")
    _cover(dialog, older, newer)
    controller.open()
    assert not _button(dialog, "exportButton").isEnabled()
    _check_row(dialog, 1)
    _button(dialog, "exportButton").click()
    path = tmp_path / "sessions.csv"
    assert path.is_file()
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == ",".join(CSV_COLUMNS)
    assert lines[1].startswith(f"1,{older},{older + 60},60,")
    assert lines[2] == ""
    assert lines[3] == ",".join(GROUP_COLUMNS)
    assert lines[4] == f",{BLANK_PROJECT},60,0.5"
    assert lines[5] == "TOTAL,,60,0.5"


def test_export_cancel_does_not_create_file(
    conn: sqlite3.Connection,
    widget: TimerWidget,
    settings_dialog: SettingsDialog,
    dialog: HistoryDialog,
    timer_controller: TimerController,
    tmp_path: Path,
) -> None:
    db.insert_session(conn, WALL_START, WALL_START + 1, 1, 0, 0.0, 0.0)
    target = tmp_path / "sessions.csv"
    controller = _make_history(
        conn, widget, settings_dialog, dialog, timer_controller, lambda: None
    )
    try:
        _cover(dialog, WALL_START)
        controller.open()
        _check_row(dialog, 0)
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
    db.insert_session(conn, WALL_START, WALL_START + 1, 1, 0, 0.0, 0.0)
    controller = _make_history(
        conn, widget, settings_dialog, dialog, timer_controller, lambda: tmp_path
    )
    try:
        _cover(dialog, WALL_START)
        controller.open()
        _check_row(dialog, 0)
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


def test_sort_start_keeps_newer_id_first_on_a_tie() -> None:
    rows = [_session(1, "a"), _session(2, "b"), _session(3, "c")]
    same_start = [
        rows[0]._replace(start_ts=10),
        rows[1]._replace(start_ts=10),
        rows[2]._replace(start_ts=5),
    ]
    ascending = sort_sessions_by_start(same_start, descending=False)
    assert [row.id for row in ascending] == [3, 2, 1]
    descending = sort_sessions_by_start(same_start, descending=True)
    assert [row.id for row in descending] == [2, 1, 3]


def test_header_sort_by_start_toggles_order(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    db.insert_session(conn, WALL_START + 300, WALL_START + 301, 1, 0, 0.0, 0.0)
    db.insert_session(conn, WALL_START + 100, WALL_START + 101, 1, 0, 0.0, 0.0)
    db.insert_session(conn, WALL_START + 200, WALL_START + 201, 1, 0, 0.0, 0.0)
    _cover(dialog, WALL_START + 100, WALL_START + 300)
    controller.open()
    header = _table(dialog).horizontalHeader()
    header.sectionClicked.emit(START_COLUMN)
    assert [_table(dialog).item(row, 1).text() for row in range(3)] == [
        format_datetime(WALL_START + 100),
        format_datetime(WALL_START + 200),
        format_datetime(WALL_START + 300),
    ]
    header.sectionClicked.emit(START_COLUMN)
    assert [_table(dialog).item(row, 1).text() for row in range(3)] == [
        format_datetime(WALL_START + 300),
        format_datetime(WALL_START + 200),
        format_datetime(WALL_START + 100),
    ]


def test_period_hides_sessions_outside_the_range(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    inside = datetime.now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    outside = inside.replace(year=inside.year - 1)
    db.insert_session(conn, int(inside.timestamp()), int(inside.timestamp()) + 10, 10, 0, 0.0, 1.0)
    db.insert_session(conn, int(outside.timestamp()), int(outside.timestamp()) + 10, 20, 0, 0.0, 2.0)
    controller.open()
    assert _table(dialog).rowCount() == 1
    assert _table(dialog).item(0, 1).text() == format_datetime(int(inside.timestamp()))
    past = QDate(outside.year, outside.month, outside.day)
    dialog.set_period(past, QDate.currentDate())
    assert _table(dialog).rowCount() == 2


def test_delete_removes_only_checked_sessions(
    controller: HistoryController,
    dialog: HistoryDialog,
    widget: TimerWidget,
    conn: sqlite3.Connection,
) -> None:
    kept = datetime.now().replace(day=1, hour=9, minute=0, second=0, microsecond=0)
    dropped = kept.replace(hour=15)
    db.insert_session(
        conn,
        int(kept.timestamp()),
        int(kept.timestamp()) + 10,
        10,
        0,
        0.0,
        1.0,
        project_number="7",
        project_name="Kitchen",
        client_name="Ivan",
    )
    db.insert_session(
        conn,
        int(dropped.timestamp()),
        int(dropped.timestamp()) + 10,
        20,
        0,
        0.0,
        2.0,
        project_number="12",
        project_name="Wardrobe",
        client_name="Anna",
    )
    controller.open()
    table = _table(dialog)
    assert table.rowCount() == 2
    assert table.item(0, 4).text() == "12"
    _check_row(dialog, 0)
    _button(dialog, "deleteButton").click()
    assert [row.project_number for row in db.list_recent_sessions(conn)] == ["7"]
    assert table.rowCount() == 1
    assert table.item(0, 4).text() == "7"
    number = widget.findChild(QComboBox, "projectNumberCombo")
    assert number is not None
    assert [number.itemText(index) for index in range(number.count())] == ["7"]


def test_select_all_deletes_only_the_visible_period(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    inside = datetime.now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    outside = inside.replace(year=inside.year - 1)
    db.insert_session(conn, int(inside.timestamp()), int(inside.timestamp()) + 5, 5, 0, 0.0, 1.0)
    kept = db.insert_session(
        conn, int(outside.timestamp()), int(outside.timestamp()) + 5, 5, 0, 0.0, 2.0
    )
    controller.open()
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None
    select_all.click()
    assert dialog.checked_ids() == (_table(dialog).item(0, 0).data(Qt.ItemDataRole.UserRole),)
    _button(dialog, "deleteButton").click()
    assert [row.id for row in db.list_recent_sessions(conn)] == [kept]


def test_selection_report_groups_checked_sessions_by_project(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    moment = datetime.now().replace(day=1, hour=10, minute=0, second=0, microsecond=0)
    start = int(moment.timestamp())
    db.insert_session(
        conn, start, start + 10, 3600, 0, 0.0, 10.0, project_number="7", project_name="Old"
    )
    db.insert_session(
        conn,
        start + 60,
        start + 70,
        1800,
        0,
        0.0,
        5.0,
        project_number="7",
        project_name="Kitchen",
    )
    db.insert_session(
        conn, start + 120, start + 130, 60, 0, 0.0, 1.0, project_number="", project_name=""
    )
    controller.open()
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None
    select_all.click()
    label = dialog.findChild(QLabel, "selectionLabel")
    assert label is not None and label.isVisible()
    assert label.text() == "\n".join(
        [
            t("history.selection.total", count=3, time=format_hms(5460), cost=16.0),
            t(
                "history.selection.project",
                number=BLANK_PROJECT,
                name=BLANK_PROJECT,
                time=format_hms(60),
                cost=1.0,
            ),
            t(
                "history.selection.project",
                number="7",
                name="Kitchen",
                time=format_hms(5400),
                cost=15.0,
            ),
        ]
    )


def test_open_session_stays_when_the_visible_period_is_deleted(
    controller: HistoryController, dialog: HistoryDialog, conn: sqlite3.Connection
) -> None:
    moment = datetime.now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    start = int(moment.timestamp())
    open_id = db.save_session(
        conn, None, start, start + 5, 5, 0, 0.0, 1.0, finalized=False, project_number="7"
    )
    db.insert_session(conn, start + 10, start + 20, 9, 0, 0.0, 2.0, project_number="7")
    controller.open()
    assert _table(dialog).rowCount() == 1
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None
    select_all.click()
    _button(dialog, "deleteButton").click()
    assert conn.execute("SELECT id, finalized FROM sessions").fetchall() == [(open_id, 0)]
    assert _empty(dialog).isVisible()
