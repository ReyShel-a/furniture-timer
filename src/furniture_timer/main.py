"""Application entry point."""

import logging
import sys

from PySide6.QtWidgets import QApplication

from furniture_timer import __version__, db, paths
from furniture_timer.logging_setup import setup_logging
from furniture_timer.settings import Settings
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)


def main() -> int:
    setup_logging(paths.log_dir())
    log.info("Furniture Timer %s starting", __version__)
    conn = db.connect()
    try:
        settings = Settings(conn)
        log.info(
            "Settings loaded: rate=%s currency=%s idle_threshold=%ss",
            settings.hourly_rate,
            settings.currency,
            settings.idle_threshold_sec,
        )
        return _run_gui(settings)
    finally:
        conn.close()


def _run_gui(settings: Settings) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    widget = TimerWidget()
    widget.show_price(settings.hourly_rate, 0.0, settings.currency)
    widget.close_clicked.connect(app.quit)
    widget.show()
    exit_code = app.exec()
    log.info("Furniture Timer exiting with code %d", exit_code)
    return exit_code
