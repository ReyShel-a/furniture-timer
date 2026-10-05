"""Place satellite windows next to the main widget."""

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

GAP_PX = 8


def place_near(window: QWidget, widget_geo: QRect) -> None:
    """Move *window* below *widget_geo*, or above if it would not fit."""
    window.adjustSize()
    size = window.frameGeometry().size()
    screens = QGuiApplication.screens()
    on_a_screen = any(widget_geo.intersects(s.availableGeometry()) for s in screens)
    primary = QGuiApplication.primaryScreen()
    if primary is None:
        return
    available = primary.availableGeometry()
    if not on_a_screen:
        window.move(available.right() - size.width(), available.bottom() - size.height())
        return
    screen = QGuiApplication.screenAt(widget_geo.center()) or primary
    available = screen.availableGeometry()
    x = widget_geo.x()
    y_below = widget_geo.bottom() + GAP_PX
    if y_below + size.height() <= available.bottom():
        y = y_below
    else:
        y = widget_geo.top() - GAP_PX - size.height()
    x = min(max(x, available.left()), available.right() - size.width())
    y = min(max(y, available.top()), available.bottom() - size.height())
    window.move(x, y)
