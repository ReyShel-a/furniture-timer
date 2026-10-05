import logging
import sys
from collections.abc import Iterator

import pytest


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
