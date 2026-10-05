from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

from furniture_timer.i18n import t
from furniture_timer.ui.widget import TimerWidget
from furniture_timer.ui.history_dialog import HISTORY_WIDTH, HistoryDialog


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def dialog(widget: TimerWidget) -> Iterator[HistoryDialog]:
    d = HistoryDialog(widget)
    yield d
    d.hide()
    d.close()
    d.deleteLater()


def _button(dialog: HistoryDialog, name: str) -> QPushButton:
    button = dialog.findChild(QPushButton, name)
    assert button is not None, name
    return button


def _label(dialog: HistoryDialog, name: str) -> QLabel:
    label = dialog.findChild(QLabel, name)
    assert label is not None, name
    return label


def _table(dialog: HistoryDialog) -> QTableWidget:
    table = dialog.findChild(QTableWidget, "historyTable")
    assert table is not None
    return table


def test_window_flags(dialog: HistoryDialog) -> None:
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    assert not (flags & Qt.WindowType.WindowDoesNotAcceptFocus)
    assert not dialog.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert dialog.width() == HISTORY_WIDTH


def test_children_and_i18n(dialog: HistoryDialog) -> None:
    assert dialog.objectName() == "HistoryDialog"
    assert dialog.windowTitle() == t("history.dialog.title")
    assert _label(dialog, "historyTitle").text() == t("history.dialog.title")
    assert _label(dialog, "emptyLabel").text() == t("history.empty")
    assert _button(dialog, "exportButton").text() == t("history.btn.export")
    assert _button(dialog, "clearButton").text() == t("history.btn.clear")
    assert _button(dialog, "closeButton").text() == t("history.btn.close")
    table = _table(dialog)
    assert [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())] == [
        t("history.col.start"),
        t("history.col.active"),
        t("history.col.cost"),
        t("history.col.project_number"),
        t("history.col.project_name"),
        t("history.col.client"),
    ]


def test_initial_empty_state(dialog: HistoryDialog) -> None:
    assert not _label(dialog, "emptyLabel").isHidden()
    assert _table(dialog).isHidden()
    assert not _button(dialog, "exportButton").isEnabled()
    assert not _button(dialog, "clearButton").isEnabled()
    assert _label(dialog, "errorLabel").isHidden()


def test_set_rows_and_empty_toggle(dialog: HistoryDialog) -> None:
    dialog.set_rows([("2026-10-05 09:07", "00:30:00", "10.00", "12", "Kitchen", "Ivan")])
    dialog.show_empty(False)
    dialog.set_export_enabled(True)
    table = _table(dialog)
    assert not table.isHidden()
    assert _label(dialog, "emptyLabel").isHidden()
    assert table.rowCount() == 1
    cells = [table.item(0, column) for column in range(6)]
    assert [cell.text() if cell is not None else None for cell in cells] == [
        "2026-10-05 09:07",
        "00:30:00",
        "10.00",
        "12",
        "Kitchen",
        "Ivan",
    ]
    assert _button(dialog, "exportButton").isEnabled()

    dialog.set_rows([])
    dialog.show_empty(True)
    dialog.set_export_enabled(False)
    assert table.rowCount() == 0
    assert table.isHidden()
    assert not _label(dialog, "emptyLabel").isHidden()
    assert not _button(dialog, "exportButton").isEnabled()


def test_show_and_clear_error(dialog: HistoryDialog) -> None:
    error = _label(dialog, "errorLabel")
    assert error.isHidden()
    dialog.show_error(t("history.error.write"))
    assert not error.isHidden()
    assert error.text() == t("history.error.write")
    dialog.clear_error()
    assert error.isHidden()
    assert error.text() == ""


def test_project_header_requests_sort(dialog: HistoryDialog) -> None:
    fired: list[str] = []
    dialog.sort_clicked.connect(lambda: fired.append("sort"))
    header = _table(dialog).horizontalHeader()
    header.sectionClicked.emit(0)
    header.sectionClicked.emit(3)
    assert fired == ["sort"]


def test_export_and_close_signals(dialog: HistoryDialog) -> None:
    fired: list[str] = []
    dialog.export_clicked.connect(lambda: fired.append("export"))
    dialog.clear_clicked.connect(lambda: fired.append("clear"))
    dialog.close_clicked.connect(lambda: fired.append("close"))
    dialog.set_export_enabled(True)
    dialog.set_clear_enabled(True)
    _button(dialog, "exportButton").click()
    _button(dialog, "clearButton").click()
    _button(dialog, "closeButton").click()
    assert fired == ["export", "clear", "close"]


def test_escape_emits_close(dialog: HistoryDialog) -> None:
    fired: list[str] = []
    dialog.close_clicked.connect(lambda: fired.append("close"))
    dialog.export_clicked.connect(lambda: fired.append("export"))
    dialog.show()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert fired == ["close"]


def test_place_near_widget(dialog: HistoryDialog, widget: TimerWidget) -> None:
    dialog.place_near(widget.frameGeometry())
    dialog.show()
    assert dialog.isVisible()
