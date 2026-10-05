"""Application entry point."""

import logging

from furniture_timer import __version__, paths
from furniture_timer.logging_setup import setup_logging

log = logging.getLogger(__name__)


def main() -> int:
    setup_logging(paths.log_dir())
    log.info("Furniture Timer %s starting", __version__)
    return 0
