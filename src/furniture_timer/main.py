"""Application entry point."""

import logging

from furniture_timer import __version__, db, paths
from furniture_timer.logging_setup import setup_logging
from furniture_timer.settings import Settings

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
    finally:
        conn.close()
    return 0
