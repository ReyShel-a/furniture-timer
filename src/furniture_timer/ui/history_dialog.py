"""Frameless history panel: sessions for a period, selection, and CSV export."""

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import QDate, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from furniture_timer.i18n import t
from furniture_timer.ui.placement import place_near as _place_near
from furniture_timer.ui.range_calendar import RangeCalendar
from furniture_timer.ui.theme import ACCENT, apply_theme, background_color

HISTORY_WIDTH = 640
_TABLE_HEIGHT = 220
_CHECK_WIDTH = 28
_COL_HEADERS = (
    "history.col.start",
    "history.col.active",
    "history.col.cost",
    "history.col.project_number",
    "history.col.project_name",
    "history.col.client",
)
CHECK_COLUMN = 0
START_COLUMN = 1
COST_COLUMN = 1 + _COL_HEADERS.index("history.col.cost")
PROJECT_COLUMN = 1 + _COL_HEADERS.index("history.col.project_number")
NAME_COLUMN = 1 + _COL_HEADERS.index("history.col.project_name")
CLIENT_COLUMN = 1 + _COL_HEADERS.index("history.col.client")
_NAME_ROLE = Qt.ItemDataRole.UserRole + 1

# id, then the six visible columns
HistoryCells = tuple[int, str, str, str, str, str, str]
ProjectChoice = tuple[str, str]


class HistoryDialog(QWidget):
    export_clicked = Signal()
    delete_clicked = Signal()
    clear_clicked = Signal()
    close_clicked = Signal()
    sort_clicked = Signal(int)
    client_changed = Signal()
    project_changed = Signal()
    period_changed = Signal()
    selection_changed = Signal()

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
        self._client_names: list[str] = []
        self._projects: list[ProjectChoice] = []
        self._checked: set[int] = set()
        self._summary_cost = ""
        self._summary_time = ""
        self._summary_client = ""
        self._summary_project = ""
        self._summary_project_name = ""

        self._title = QLabel(t("history.dialog.title"), self)
        self._title.setObjectName("historyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._card = QWidget(self)
        self._card.setObjectName("summaryCard")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._cost_caption = self._make_caption("summaryCostCaption", t("history.summary.cost"))
        self._cost = self._make_caption("summaryCost", "")
        self._time = self._make_caption("summaryTime", "")
        self._caption = self._make_caption("summaryCaption", t("history.summary.pick"))
        card = QVBoxLayout(self._card)
        card.setContentsMargins(12, 10, 12, 10)
        card.setSpacing(0)
        card.addWidget(self._cost_caption)
        card.addWidget(self._cost)
        card.addWidget(self._time)
        card.addWidget(self._caption)

        self._table = QTableWidget(0, 1 + len(_COL_HEADERS), self)
        self._table.setObjectName("historyTable")
        self._table.setHorizontalHeaderLabels(self._header_labels())
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setAlternatingRowColors(True)
        self._table.setFixedHeight(_TABLE_HEIGHT)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(CHECK_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(NAME_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(CLIENT_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(36)
        self._table.setColumnWidth(CHECK_COLUMN, _CHECK_WIDTH)
        header.setHighlightSections(False)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_section_clicked)
        self._table.itemChanged.connect(self._on_item_changed)

        self._select_all = QCheckBox(t("history.select_all"), self)
        self._select_all.setObjectName("selectAll")
        self._select_all.setTristate(True)
        self._select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_all.clicked.connect(self._on_select_all_clicked)

        self._client = QComboBox(self)
        self._client.setObjectName("summaryClient")
        self._client.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._project = QComboBox(self)
        self._project.setObjectName("summaryProject")
        self._project.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._calendar = RangeCalendar(self)
        self._calendar.range_changed.connect(self.period_changed)
        self._client.currentIndexChanged.connect(self._on_client_changed)
        self._project.currentIndexChanged.connect(self._on_project_changed)
        self._fill_clients()
        self._fill_projects()

        self._empty = QLabel(t("history.empty.period"), self)
        self._empty.setObjectName("emptyLabel")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()

        self._error = QLabel(self)
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)
        self._error.hide()

        self._export = self._make_button("exportButton", t("history.btn.export"))
        self._delete = self._make_button("deleteButton", t("history.btn.delete"))
        self._clear = self._make_button("clearButton", t("history.btn.clear"))
        self._close = self._make_button("closeButton", t("history.btn.close"))
        self._export.clicked.connect(self.export_clicked)
        self._delete.clicked.connect(self.delete_clicked)
        self._clear.clicked.connect(self.clear_clicked)
        self._close.clicked.connect(self.close_clicked)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self._export, 1)
        buttons.addWidget(self._delete, 1)
        buttons.addWidget(self._clear, 1)
        buttons.addWidget(self._close, 1)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        filters.addWidget(self._client, 1)
        filters.addWidget(self._project, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        root.addWidget(self._title)
        root.addWidget(self._card)
        root.addLayout(filters)
        root.addWidget(self._calendar)
        root.addWidget(self._table)
        root.addWidget(self._empty)
        root.addWidget(self._select_all)
        self._selection = QLabel(self)
        self._selection.setObjectName("selectionLabel")
        self._selection.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._selection.setWordWrap(True)
        self._selection.hide()
        root.addWidget(self._selection)
        root.addWidget(self._error)
        root.addLayout(buttons)
        apply_theme(self)
        self._apply_summary()
        self.show_empty(True)
        self.set_export_enabled(False)
        self.set_delete_enabled(False)
        self.set_clear_enabled(False)
        self._sync_select_all()

    def set_rows(self, rows: Sequence[HistoryCells]) -> None:
        """Replace the table. Checks survive only for ids that are still shown."""
        visible = {row[0] for row in rows}
        self._checked &= visible
        self._table.blockSignals(True)
        self._table.setRowCount(len(rows))
        for row_index, (row_id, *values) in enumerate(rows):
            check = QTableWidgetItem()
            check.setData(Qt.ItemDataRole.UserRole, row_id)
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(
                Qt.CheckState.Checked if row_id in self._checked else Qt.CheckState.Unchecked
            )
            check.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row_index, CHECK_COLUMN, check)
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if column in (NAME_COLUMN, CLIENT_COLUMN):
                    align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                else:
                    align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                item.setTextAlignment(align)
                if column == COST_COLUMN:
                    item.setForeground(QBrush(QColor(ACCENT)))
                self._table.setItem(row_index, column, item)
        self._table.blockSignals(False)
        self._sync_select_all()

    def checked_ids(self) -> tuple[int, ...]:
        """Checked session ids in the order of the visible rows."""
        ordered: list[int] = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, CHECK_COLUMN)
            if item is None:
                continue
            row_id = int(item.data(Qt.ItemDataRole.UserRole))
            if row_id in self._checked:
                ordered.append(row_id)
        return tuple(ordered)

    def show_empty(self, empty: bool = True) -> None:
        self._empty.setVisible(empty)
        self._table.setVisible(not empty)

    def set_export_enabled(self, enabled: bool) -> None:
        self._export.setEnabled(enabled)

    def set_delete_enabled(self, enabled: bool) -> None:
        self._delete.setEnabled(enabled)

    def set_clear_enabled(self, enabled: bool) -> None:
        self._clear.setEnabled(enabled)

    def set_client_choices(self, names: Sequence[str]) -> None:
        """Replace client names. The current choice stays when it is still listed."""
        self._client_names = [name for name in names if name.strip()]
        self._fill_clients()

    def set_project_choices(self, projects: Sequence[ProjectChoice]) -> None:
        """Replace projects of the selected client. An unknown number falls back to all."""
        self._projects = [
            (number, name) for number, name in projects if number.strip()
        ]
        self._fill_projects()

    def selected_client(self) -> str:
        data = self._client.currentData()
        return "" if data is None else str(data)

    def selected_project(self) -> str:
        data = self._project.currentData()
        return "" if data is None else str(data)

    def selected_project_name(self) -> str:
        index = self._project.currentIndex()
        if index < 0:
            return ""
        data = self._project.itemData(index, _NAME_ROLE)
        return "" if not data else str(data)

    def period_bounds(self) -> tuple[int, int]:
        """Inclusive local-day unix bounds of the committed calendar range."""
        start, end = self._calendar.bounds()
        return (_day_start(start), _day_end(end))

    def period_label(self) -> str:
        return self._calendar.period_text()

    def set_period(self, start: QDate, end: QDate) -> None:
        self._calendar.set_period(start, end)

    def show_summary(
        self,
        cost: str,
        time_text: str,
        client: str,
        project: str = "",
        project_name: str = "",
    ) -> None:
        """Show the client total. An empty client leaves the prompt and hides the figures."""
        self._summary_cost = cost
        self._summary_time = time_text
        self._summary_client = client
        self._summary_project = project
        self._summary_project_name = project_name
        self._apply_summary()

    def show_selection(self, text: str) -> None:
        self._selection.setText(text)
        self._selection.setVisible(bool(text.strip()))

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
        self._table.setHorizontalHeaderLabels(self._header_labels())
        self._empty.setText(t("history.empty.period"))
        self._select_all.setText(t("history.select_all"))
        self._cost_caption.setText(t("history.summary.cost"))
        self._calendar.apply_language()
        self._fill_clients()
        self._fill_projects()
        self._apply_summary()
        self._export.setText(t("history.btn.export"))
        self._delete.setText(t("history.btn.delete"))
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
        if index in (START_COLUMN, PROJECT_COLUMN):
            self.sort_clicked.emit(index)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != CHECK_COLUMN:
            return
        row_id = item.data(Qt.ItemDataRole.UserRole)
        if row_id is None:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._checked.add(int(row_id))
        else:
            self._checked.discard(int(row_id))
        self._sync_select_all()
        self.selection_changed.emit()

    def _on_select_all_clicked(self, _checked: bool = False) -> None:
        ids = set(self._row_ids())
        if ids and ids <= self._checked:
            self._checked -= ids
        else:
            self._checked.update(ids)
        self._apply_checks()
        self._sync_select_all()
        self.selection_changed.emit()

    def _on_client_changed(self, _index: int = 0) -> None:
        self._sync_project_enabled()
        self.client_changed.emit()

    def _on_project_changed(self, _index: int = 0) -> None:
        self.project_changed.emit()

    def _apply_summary(self) -> None:
        if not self._summary_client:
            self._cost_caption.hide()
            self._cost.hide()
            self._time.hide()
            self._caption.setText(t("history.summary.pick"))
        else:
            self._cost_caption.show()
            self._cost.setText(self._summary_cost)
            self._cost.show()
            self._time.setText(self._summary_time)
            self._time.show()
            period = self.period_label()
            if self._summary_project:
                label = self._summary_project
                name = self._summary_project_name.strip()
                if name:
                    label = f"{label} {name}"
                self._caption.setText(
                    t(
                        "history.summary.caption.project",
                        client=self._summary_client,
                        number=label,
                        period=period,
                    )
                )
            else:
                self._caption.setText(
                    t(
                        "history.summary.caption",
                        client=self._summary_client,
                        period=period,
                    )
                )
        if self.isVisible():
            self.adjustSize()

    def _apply_checks(self) -> None:
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, CHECK_COLUMN)
            if item is None:
                continue
            row_id = int(item.data(Qt.ItemDataRole.UserRole))
            item.setCheckState(
                Qt.CheckState.Checked if row_id in self._checked else Qt.CheckState.Unchecked
            )
        self._table.blockSignals(False)

    def _sync_select_all(self) -> None:
        ids = set(self._row_ids())
        self._select_all.blockSignals(True)
        self._select_all.setEnabled(bool(ids))
        if not ids or not (ids & self._checked):
            state = Qt.CheckState.Unchecked
        elif ids <= self._checked:
            state = Qt.CheckState.Checked
        else:
            state = Qt.CheckState.PartiallyChecked
        self._select_all.setCheckState(state)
        self._select_all.blockSignals(False)

    def _sync_project_enabled(self) -> None:
        self._project.setEnabled(bool(self.selected_client()))

    def _row_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, CHECK_COLUMN)
            if item is None:
                continue
            ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return tuple(ids)

    def _header_labels(self) -> list[str]:
        return [""] + [t(key) for key in _COL_HEADERS]

    def _fill_clients(self) -> None:
        current = self.selected_client()
        self._client.blockSignals(True)
        self._client.clear()
        self._client.addItem(t("history.summary.pick"), "")
        for name in self._client_names:
            self._client.addItem(name, name)
        index = self._client.findData(current)
        self._client.setCurrentIndex(0 if index < 0 else index)
        self._client.blockSignals(False)
        self._sync_project_enabled()

    def _fill_projects(self) -> None:
        current = self.selected_project()
        self._project.blockSignals(True)
        self._project.clear()
        self._project.addItem(t("history.filter.project.all"), "")
        for number, name in self._projects:
            label = number if not name.strip() else f"{number} · {name}"
            self._project.addItem(label, number)
            self._project.setItemData(self._project.count() - 1, name, _NAME_ROLE)
        index = self._project.findData(current)
        self._project.setCurrentIndex(0 if index < 0 else index)
        self._project.blockSignals(False)
        self._sync_project_enabled()

    def _make_caption(self, name: str, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        return label

    def _make_button(self, name: str, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button


def _day_start(day: QDate) -> int:
    return int(datetime(day.year(), day.month(), day.day()).timestamp())


def _day_end(day: QDate) -> int:
    return int(datetime(day.year(), day.month(), day.day(), 23, 59, 59).timestamp())
