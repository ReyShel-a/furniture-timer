"""Application entry point."""

import logging
import sqlite3
import sys

from PySide6.QtWidgets import QApplication

from furniture_timer import __version__, db, paths
from furniture_timer.i18n import set_language
from furniture_timer.idle import create_idle_detector
from furniture_timer.logging_setup import setup_logging
from furniture_timer.settings import Settings
from furniture_timer.timer_model import SessionResult, TimerModel
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.history_controller import HistoryController
from furniture_timer.ui.history_dialog import HistoryDialog
from furniture_timer.ui.idle_controller import IdleController
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.settings_controller import SettingsController
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.tray_controller import TrayController
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)


def main() -> int:
    setup_logging(paths.log_dir())
    log.info("Furniture Timer %s starting", __version__)
    conn = db.connect()
    try:
        settings = Settings(conn)
        log.info(
            "Settings loaded: rate=%s currency=%s idle_threshold=%ss language=%s",
            settings.hourly_rate,
            settings.currency,
            settings.idle_threshold_sec,
            settings.language,
        )
        return _run_gui(settings, conn)
    finally:
        conn.close()


def _persist_session(
    conn: sqlite3.Connection,
    result: SessionResult,
    rate_snapshot: float,
    cost: float,
    project_number: str = "",
    project_name: str = "",
    client_name: str = "",
) -> None:
    db.insert_session(
        conn,
        start_ts=result.start_ts,
        end_ts=result.end_ts,
        active_seconds=result.active_seconds,
        idle_seconds=result.idle_seconds,
        rate_snapshot=rate_snapshot,
        cost=cost,
        project_number=project_number,
        project_name=project_name,
        client_name=client_name,
    )


def _load_job_suggestions(conn: sqlite3.Connection, widget: TimerWidget) -> None:
    try:
        widget.set_job_suggestions(db.list_known_projects(conn), db.list_known_clients(conn))
    except Exception:
        log.exception("Failed to load project suggestions")


def _run_gui(settings: Settings, conn: sqlite3.Connection) -> int:
    set_language(settings.language)
    app = QApplication.instance() or QApplication(sys.argv)
    widget = TimerWidget()
    model = TimerModel()
    timer_controller = TimerController(
        model,
        widget,
        hourly_rate=lambda: settings.hourly_rate,
        currency=lambda: settings.currency,
        persist_session=lambda result, rate, cost: _persist_session(
            conn, result, rate, cost, *widget.job()
        ),
        parent=app,
    )
    detector = create_idle_detector()
    dialog = IdleDialog(widget)
    IdleController(
        model,
        widget,
        dialog,
        detector,
        threshold=lambda: float(settings.idle_threshold_sec),
        timer_controller=timer_controller,
        parent=app,
    )
    settings_dialog = SettingsDialog(widget)
    settings_controller = SettingsController(
        settings,
        widget,
        settings_dialog,
        timer_controller,
        parent=app,
    )
    history_dialog = HistoryDialog(widget)
    HistoryController(
        conn,
        widget,
        settings_dialog,
        history_dialog,
        timer_controller,
        parent=app,
    )
    tray = TrayController(widget, timer_controller, parent=app)

    def _retranslate() -> None:
        widget.retranslate()
        dialog.retranslate()
        settings_dialog.retranslate()
        history_dialog.retranslate()
        tray.retranslate()
        timer_controller.refresh()

    _load_job_suggestions(conn, widget)
    timer_controller.state_changed.connect(
        lambda: _load_job_suggestions(conn, widget)
    )
    settings_controller.language_changed.connect(_retranslate)
    if tray.active:
        app.setQuitOnLastWindowClosed(False)
        widget.close_clicked.connect(tray.hide_widget)
    else:
        widget.close_clicked.connect(app.quit)
    tray.quit_requested.connect(app.quit)
    app.aboutToQuit.connect(detector.stop)
    widget.show()
    exit_code = app.exec()
    log.info("Furniture Timer exiting with code %d", exit_code)
    return exit_code
