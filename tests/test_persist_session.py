import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from furniture_timer import db
from furniture_timer.main import _persist_session
from furniture_timer.timer_model import SessionResult, TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
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
def model(clock: FakeClock) -> TimerModel:
    return TimerModel(clock=clock, wall_clock=clock.wall)


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = db.connect(tmp_path / "db.sqlite")
    try:
        yield connection
    finally:
        connection.close()


def _click(widget: TimerWidget, name: str) -> None:
    button = widget.findChild(QPushButton, name)
    assert button is not None, name
    button.click()


def _sessions(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        "SELECT start_ts, end_ts, active_seconds, idle_seconds, "
        "rate_snapshot, cost, note FROM sessions ORDER BY id"
    ).fetchall()


def _controller(
    model: TimerModel,
    widget: TimerWidget,
    conn: sqlite3.Connection,
    rate: float = RATE,
) -> TimerController:
    return TimerController(
        model,
        widget,
        hourly_rate=lambda: rate,
        persist_session=lambda result, snap, cost: _persist_session(
            conn, result, snap, cost
        ),
    )


def test_stop_writes_active_seconds_and_cost(
    model: TimerModel,
    widget: TimerWidget,
    clock: FakeClock,
    conn: sqlite3.Connection,
) -> None:
    controller = _controller(model, widget, conn)
    try:
        _click(widget, "startPauseButton")
        clock.advance(1800)
        _click(widget, "stopButton")
    finally:
        controller.deleteLater()

    rows = _sessions(conn)
    assert len(rows) == 1
    start_ts, end_ts, active_seconds, idle_seconds, rate_snapshot, cost, note = rows[0]
    assert start_ts == int(WALL_START)
    assert end_ts == int(WALL_START + 1800)
    assert active_seconds == 1800
    assert idle_seconds == 0
    assert rate_snapshot == RATE
    assert cost == 10.0
    assert note == ""
    assert model.state is TimerState.IDLE


def test_stop_persists_zero_length_session(
    model: TimerModel,
    widget: TimerWidget,
    conn: sqlite3.Connection,
) -> None:
    controller = _controller(model, widget, conn)
    try:
        _click(widget, "startPauseButton")
        _click(widget, "stopButton")
    finally:
        controller.deleteLater()

    rows = _sessions(conn)
    assert len(rows) == 1
    start_ts, end_ts, active_seconds, idle_seconds, rate_snapshot, cost, note = rows[0]
    assert start_ts == int(WALL_START)
    assert end_ts == int(WALL_START)
    assert active_seconds == 0
    assert idle_seconds == 0
    assert rate_snapshot == RATE
    assert cost == 0.0
    assert note == ""


def test_stop_in_idle_does_not_write_a_row(
    model: TimerModel,
    widget: TimerWidget,
    conn: sqlite3.Connection,
) -> None:
    controller = _controller(model, widget, conn)
    try:
        widget.stop_clicked.emit()
    finally:
        controller.deleteLater()

    assert _sessions(conn) == []
    assert model.state is TimerState.IDLE


def test_persist_failure_still_resets_ui(
    model: TimerModel,
    widget: TimerWidget,
    clock: FakeClock,
) -> None:
    def boom(_result: SessionResult, _rate: float, _cost: float) -> None:
        raise RuntimeError("disk full")

    controller = TimerController(model, widget, persist_session=boom)
    try:
        _click(widget, "startPauseButton")
        clock.advance(10)
        _click(widget, "stopButton")
        assert model.state is TimerState.IDLE
        stop_button = widget.findChild(QPushButton, "stopButton")
        assert stop_button is not None
        assert not stop_button.isEnabled()
    finally:
        controller.deleteLater()


def test_stop_writes_project_and_client(
    model: TimerModel,
    widget: TimerWidget,
    conn: sqlite3.Connection,
) -> None:
    controller = TimerController(
        model,
        widget,
        hourly_rate=lambda: RATE,
        persist_session=lambda result, rate, cost: _persist_session(
            conn, result, rate, cost, *widget.job()
        ),
    )
    try:
        for name, text in (
            ("projectNumberCombo", "12"),
            ("projectNameCombo", "Kitchen"),
            ("clientNameCombo", "Ivan"),
        ):
            combo = widget.findChild(QComboBox, name)
            assert combo is not None, name
            combo.setEditText(text)
        _click(widget, "startPauseButton")
        _click(widget, "stopButton")
    finally:
        controller.deleteLater()

    row = conn.execute(
        "SELECT project_number, project_name, client_name FROM sessions"
    ).fetchone()
    assert row == ("12", "Kitchen", "Ivan")


def test_number_choice_fills_latest_name(widget: TimerWidget) -> None:
    widget.set_job_suggestions([("12", "Wardrobe"), ("7", "Kitchen")], ["Ivan"])
    number = widget.findChild(QComboBox, "projectNumberCombo")
    name = widget.findChild(QComboBox, "projectNameCombo")
    assert number is not None and name is not None
    index = number.findText("12")
    number.setCurrentIndex(index)
    number.activated[int].emit(index)
    assert name.currentText() == "Wardrobe"


def test_unique_name_choice_fills_number(widget: TimerWidget) -> None:
    widget.set_job_suggestions([("12", "Wardrobe"), ("7", "Kitchen")], ["Ivan"])
    number = widget.findChild(QComboBox, "projectNumberCombo")
    name = widget.findChild(QComboBox, "projectNameCombo")
    assert number is not None and name is not None
    index = name.findText("Kitchen")
    name.setCurrentIndex(index)
    name.activated[int].emit(index)
    assert number.currentText() == "7"


def test_shared_name_does_not_change_number(widget: TimerWidget) -> None:
    widget.set_job_suggestions([("12", "Kitchen"), ("7", "Kitchen")], [])
    number = widget.findChild(QComboBox, "projectNumberCombo")
    name = widget.findChild(QComboBox, "projectNameCombo")
    assert number is not None and name is not None
    number.setEditText("kept")
    name.setCurrentIndex(0)
    name.activated[int].emit(0)
    assert number.currentText() == "kept"


def test_main_persist_helper_inserts_row(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        result = SessionResult(
            start_ts=100, end_ts=200, active_seconds=60, idle_seconds=5
        )
        _persist_session(conn, result, rate_snapshot=30.0, cost=0.5)
        assert _sessions(conn) == [(100, 200, 60, 5, 30.0, 0.5, "")]
    finally:
        conn.close()
