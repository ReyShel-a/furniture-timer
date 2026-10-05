"""Dark theme: SPEC colors and the shared Qt stylesheet."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

BG = "#1e1e1e"
FG = "#e0e0e0"
ACCENT = "#4caf50"
DANGER = "#e53935"

ACCENT_HOVER = "#66bb6a"
DANGER_HOVER = "#ef5350"
SURFACE = "#2d2d2d"
SURFACE_HOVER = "#3a3a3a"
MUTED = "#6b6b6b"
DANGER_MUTED = "#c06060"
ON_COLOR = "#ffffff"
BG_OPACITY = 0.75


def background_color() -> QColor:
    """Window fill; painted by the widget because QSS backgrounds are skipped on translucent windows."""
    color = QColor(BG)
    color.setAlphaF(BG_OPACITY)
    return color


# One installed family per platform: any family Qt cannot resolve (or a glyph
# missing from the font) triggers a full font-database scan, ~+45 MB RAM on Windows.
_PLATFORM_FONTS: dict[str, tuple[str, str]] = {
    "win32": ('"Consolas"', '"Segoe UI Symbol"'),
    "darwin": ('"Menlo"', '"Apple Symbols"'),
}
MONO_FONT, SYMBOL_FONT = _PLATFORM_FONTS.get(
    sys.platform, ('"DejaVu Sans Mono"', '"DejaVu Sans"')
)

DARK_QSS = f"""
QLabel {{
    color: {FG};
    background: transparent;
}}
#timeLabel {{
    font-family: {MONO_FONT};
    font-size: 28pt;
}}
#priceLabel {{
    font-size: 14pt;
}}
QPushButton {{
    color: {FG};
    background-color: {SURFACE};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 10pt;
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
}}
QPushButton:disabled {{
    color: {MUTED};
    background-color: {SURFACE};
}}
#startPauseButton {{
    color: {ON_COLOR};
    background-color: {ACCENT};
}}
#startPauseButton:hover {{
    background-color: {ACCENT_HOVER};
}}
#stopButton {{
    color: {ON_COLOR};
    background-color: {DANGER};
}}
#stopButton:hover {{
    background-color: {DANGER_HOVER};
}}
#stopButton:disabled {{
    color: {DANGER_MUTED};
    background-color: {SURFACE};
    border: 1px solid {DANGER};
    padding: 3px 7px;
}}
#settingsButton {{
    font-family: {SYMBOL_FONT};
    font-size: 12pt;
    padding: 2px 0;
}}
#closeButton:hover {{
    color: {ON_COLOR};
    background-color: {DANGER};
}}
QToolTip {{
    color: {FG};
    background-color: {SURFACE};
    border: 1px solid {SURFACE_HOVER};
}}
QLineEdit {{
    color: {FG};
    background-color: {SURFACE};
    border: 1px solid {SURFACE_HOVER};
    border-radius: 4px;
    padding: 4px 6px;
    font-size: 10pt;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox {{
    color: {FG};
    background-color: {SURFACE};
    border: 1px solid {SURFACE_HOVER};
    border-radius: 4px;
    padding: 4px 6px;
    font-size: 10pt;
}}
QComboBox QAbstractItemView {{
    color: {FG};
    background-color: {SURFACE};
    selection-background-color: {ACCENT};
    selection-color: {ON_COLOR};
    border: 1px solid {SURFACE_HOVER};
}}
#errorLabel {{
    color: {DANGER};
    font-size: 9pt;
}}
QTableWidget {{
    color: {FG};
    background-color: {SURFACE};
    border: 1px solid {SURFACE_HOVER};
    border-radius: 4px;
    gridline-color: {SURFACE_HOVER};
    font-size: 8pt;
    selection-background-color: {SURFACE};
    selection-color: {FG};
}}
QTableWidget::item {{
    padding: 2px;
}}
QHeaderView::section {{
    color: {FG};
    background-color: {SURFACE};
    border: none;
    border-bottom: 1px solid {SURFACE_HOVER};
    padding: 4px 2px;
    font-size: 8pt;
}}
QTableCornerButton::section {{
    background-color: {SURFACE};
    border: none;
}}
"""


def apply_theme(widget: QWidget) -> None:
    """Apply the dark stylesheet to a top-level widget; children inherit it.

    Must run before the first show(): translucency is fixed at window creation.
    """
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    widget.setStyleSheet(DARK_QSS)
