"""Frameless history panel: last sessions table + CSV export. No business logic."""

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import QDate, QRect, Qt, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
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

HISTORY_WIDTH = 520
_TABLE_HEIGHT = 180
_COL_HEADERS = (
    "history.col.start",
    "history.col.active",
    "history.col.cost",
    "history.col.project_number",
    "history.col.project_name",
    "history.col.client",
)
_PROJECT_COLUMN = _COL_HEADERS.index("history.col.project_number")


class HistoryDialog(QWidget):
    export_clicked = Signal()
    clear_clicked = Signal()
    close_clicked = Signal()
    sort_clicked = Signal()
    summary_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryDialog")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setFixedWidth(HISTORY_WIDTH)
        self.setWindowTitle(t("history.dialog.title"))
        self._background = background_color()
        self._project_numbers: list[str] = []

        self._title = QLabel(t("history.dialog.title"), self)
        self._title.setObjectName("historyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._table = QTableWidget(0, len(_COL_HEADERS), self)
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
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_section_clicked)

        self._project = QComboBox(self)
        self._project.setObjectName("summaryProject")
        self._from_label = self._make_caption("periodFromLabel", t("history.period.from"))
        self._from = self._make_date("periodFrom")
        self._to_label = self._make_caption("periodToLabel", t("history.period.to"))
        self._to = self._make_date("periodTo")
        today = QDate.currentDate()
        self._from.setDate(QDate(today.year(), today.month(), 1))
        self._to.setDate(today)
        self._summary = QLabel(t("history.summary.pick"), self)
        self._summary.setObjectName("summaryLabel")
        self._summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._summary.setWordWrap(True)
        self._project.currentIndexChanged.connect(self.summary_changed)
        self._from.dateChanged.connect(self.summary_changed)
        self._to.dateChanged.connect(self.summary_changed)
        self._fill_projects()

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
        self._clear = self._make_button("clearButton", t("history.btn.clear"))
        self._close = self._make_button("closeButton", t("history.btn.close"))
        self._export.clicked.connect(self.export_clicked)
        self._clear.clicked.connect(self.clear_clicked)
        self._close.clicked.connect(self.close_clicked)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self._export, 1)
        buttons.addWidget(self._clear, 1)
        buttons.addWidget(self._close, 1)

        period = QHBoxLayout()
        period.setSpacing(4)
        period.addWidget(self._project, 1)
        period.addWidget(self._from_label)
        period.addWidget(self._from)
        period.addWidget(self._to_label)
        period.addWidget(self._to)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        root.addWidget(self._title)
        root.addWidget(self._table)
        root.addWidget(self._empty)
        root.addLayout(period)
        root.addWidget(self._summary)
        root.addWidget(self._error)
        root.addLayout(buttons)
        apply_theme(self)
        self.show_empty(True)
        self.set_export_enabled(False)
        self.set_clear_enabled(False)

    def set_rows(self, rows: Sequence[tuple[str, str, str, str, str, str]]) -> None:
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

    def set_clear_enabled(self, enabled: bool) -> None:
        self._clear.setEnabled(enabled)

    def set_project_choices(self, numbers: Sequence[str]) -> None:
        """Replace project numbers. The current choice stays when it is still listed."""
        self._project_numbers = [number for number in numbers if number.strip()]
        self._fill_projects()

    def selected_project(self) -> str:
        data = self._project.currentData()
        return "" if data is None else str(data)

    def period_bounds(self) -> tuple[int, int]:
        """Inclusive local-day unix bounds. Swaps the dates when from is after to."""
        start = self._from.date()
        end = self._to.date()
        if start > end:
            start, end = end, start
        return (_day_start(start), _day_end(end))

    def show_summary(self, text: str) -> None:
        self._summary.setText(text)

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
        self._from_label.setText(t("history.period.from"))
        self._to_label.setText(t("history.period.to"))
        self._fill_projects()
        if not self.selected_project():
            self.show_summary(t("history.summary.pick"))
        self._export.setText(t("history.btn.export"))
        self._clear.setText(t("history.btn.clear"))
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

    def _on_section_clicked(self, index: int) -> None:
        if index == _PROJECT_COLUMN:
            self.sort_clicked.emit()

    def _fill_projects(self) -> None:
        current = self.selected_project()
        self._project.blockSignals(True)
        self._project.clear()
        self._project.addItem(t("history.summary.pick"), "")
        for number in self._project_numbers:
            self._project.addItem(number, number)
        index = self._project.findData(current)
        self._project.setCurrentIndex(0 if index < 0 else index)
        self._project.blockSignals(False)

    def _make_caption(self, name: str, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName(name)
        return label

    def _make_date(self, name: str) -> QDateEdit:
        edit = QDateEdit(self)
        edit.setObjectName(name)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        return edit

    def _make_button(self, name: str, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button


def _day_start(day: QDate) -> int:
    return int(datetime(day.year(), day.month(), day.day()).timestamp())


def _day_end(day: QDate) -> int:
    return int(datetime(day.year(), day.month(), day.day(), 23, 59, 59).timestamp())
