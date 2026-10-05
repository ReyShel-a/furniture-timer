import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import logging  # noqa: E402
import sys  # noqa: E402
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

pytest_plugins = ["tests.idle_fixtures"]


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    from furniture_timer.i18n import set_language

    set_language("en")
    yield
    set_language("en")


@pytest.fixture(autouse=True)
def _isolate_root_logging() -> Iterator[None]:
    root = logging.getLogger()
    before = list(root.handlers)
    excepthook = sys.excepthook
    yield
    sys.excepthook = excepthook
    for handler in list(root.handlers):
        if handler not in before:
            root.removeHandler(handler)
            handler.close()
