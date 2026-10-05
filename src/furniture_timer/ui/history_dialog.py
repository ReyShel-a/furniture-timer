"""Frameless history panel: last sessions table + CSV export. No business logic."""

from collections.abc import Sequence

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from furniture_timer.i18n import t
from furniture_timer.ui.placement import place_near as _place_near
from furniture_timer.ui.theme import apply_theme, background_color
from furniture_timer.ui.widget import WIDGET_WIDTH

_TABLE_HEIGHT = 180
_COL_HEADERS = ("history.col.start", "history.col.active", "history.col.cost")


class HistoryDialog(QWidget):
    export_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryDialog")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setFixedWidth(WIDGET_WIDTH)
        self.setWindowTitle(t("history.dialog.title"))
        self._background = background_color()

        self._title = QLabel(t("history.dialog.title"), self)
        self._title.setObjectName("historyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._table = QTableWidget(0, 3, self)
        self._table.setObjectName("historyTable")
        self._table.setHorizontalHeaderLabels([t(key) for key in _COL_HEADERS])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)
        self._table.setFixedHeight(_TABLE_HEIGHT)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setHighlightSections(False)

        self._empty = QLabel(t("history.empty"), self)
        self._empty.setObjectName("emptyLabel")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()

        self._error = QLabel(self)
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)
        self._error.hide()

        self._export = self._make_button("exportButton", t("history.btn.export"))
        self._close = self._make_button("closeButton", t("history.btn.close"))
        self._export.clicked.connect(self.export_clicked)
        self._close.clicked.connect(self.close_clicked)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self._export, 1)
        buttons.addWidget(self._close, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        root.addWidget(self._title)
        root.addWidget(self._table)
        root.addWidget(self._empty)
        root.addWidget(self._error)
        root.addLayout(buttons)
        apply_theme(self)
        self.show_empty(True)
        self.set_export_enabled(False)

    def set_rows(self, rows: Sequence[tuple[str, str, str]]) -> None:
        self._table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_index, column, item)

    def show_empty(self, empty: bool = True) -> None:
        self._empty.setVisible(empty)
        self._table.setVisible(not empty)

    def set_export_enabled(self, enabled: bool) -> None:
        self._export.setEnabled(enabled)

    def show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()

    def clear_error(self) -> None:
        self._error.clear()
        self._error.hide()

    def place_near(self, widget_geo: QRect) -> None:
        _place_near(self, widget_geo)

    def retranslate(self) -> None:
        self.setWindowTitle(t("history.dialog.title"))
        self._title.setText(t("history.dialog.title"))
        self._table.setHorizontalHeaderLabels([t(key) for key in _COL_HEADERS])
        self._empty.setText(t("history.empty"))
        self._export.setText(t("history.btn.export"))
        self._close.setText(t("history.btn.close"))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._background)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _make_button(self, name: str, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button
