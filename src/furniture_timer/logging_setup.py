"""File-only logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from furniture_timer.paths import LOG_FILENAME

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_MAX_BYTES = 512 * 1024
_BACKUP_COUNT = 2


def setup_logging(directory: Path, level: int = logging.INFO) -> RotatingFileHandler:
    """Attach a rotating file handler to the root logger; idempotent per file."""
    directory.mkdir(parents=True, exist_ok=True)
    log_file = str((directory / LOG_FILENAME).resolve())
    root = logging.getLogger()
    for existing in root.handlers:
        if isinstance(existing, RotatingFileHandler) and existing.baseFilename == log_file:
            return existing

    handler = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
    logging.captureWarnings(True)
    sys.excepthook = _log_uncaught
    return handler


def _log_uncaught(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    logging.getLogger("furniture_timer").critical(
        "Uncaught exception", exc_info=(exc_type, exc, tb)
    )
