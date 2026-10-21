from collections.abc import Iterator
from datetime import datetime

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QPushButton, QTableWidget

from furniture_timer.ui.range_calendar import RangeCalendar

from furniture_timer.i18n import t
from furniture_timer.ui.widget import TimerWidget
from furniture_timer.ui.history_dialog import HISTORY_WIDTH, START_COLUMN, HistoryDialog


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
    assert _label(dialog, "emptyLabel").text() == t("history.empty.period")
    assert _button(dialog, "exportButton").text() == t("history.btn.export")
    assert _button(dialog, "deleteButton").text() == t("history.btn.delete")
    assert _button(dialog, "clearButton").text() == t("history.btn.clear")
    assert _button(dialog, "closeButton").text() == t("history.btn.close")
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None
    assert select_all.text() == t("history.select_all")
    table = _table(dialog)
    assert [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())] == [
        "",
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
    assert not _button(dialog, "deleteButton").isEnabled()
    assert not _button(dialog, "clearButton").isEnabled()
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None and not select_all.isEnabled()
    assert _label(dialog, "errorLabel").isHidden()
    selection = dialog.findChild(QLabel, "selectionLabel")
    assert selection is not None and selection.isHidden()


def test_set_rows_and_empty_toggle(dialog: HistoryDialog) -> None:
    dialog.set_rows([(7, "2026-10-05 09:07", "00:30:00", "10.00", "12", "Kitchen", "Ivan")])
    dialog.show_empty(False)
    dialog.set_export_enabled(True)
    table = _table(dialog)
    assert not table.isHidden()
    assert _label(dialog, "emptyLabel").isHidden()
    assert table.rowCount() == 1
    check = table.item(0, 0)
    assert check is not None
    assert check.data(Qt.ItemDataRole.UserRole) == 7
    assert check.checkState() == Qt.CheckState.Unchecked
    cells = [table.item(0, column) for column in range(1, 7)]
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
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None and not select_all.isEnabled()


def test_show_and_clear_error(dialog: HistoryDialog) -> None:
    error = _label(dialog, "errorLabel")
    assert error.isHidden()
    dialog.show_error(t("history.error.write"))
    assert not error.isHidden()
    assert error.text() == t("history.error.write")
    dialog.clear_error()
    assert error.isHidden()
    assert error.text() == ""


def test_date_and_project_headers_request_sort(dialog: HistoryDialog) -> None:
    fired: list[int] = []
    dialog.sort_clicked.connect(fired.append)
    header = _table(dialog).horizontalHeader()
    header.sectionClicked.emit(0)
    header.sectionClicked.emit(START_COLUMN)
    header.sectionClicked.emit(2)
    header.sectionClicked.emit(4)
    assert fired == [START_COLUMN, 4]


def test_export_delete_and_close_signals(dialog: HistoryDialog) -> None:
    fired: list[str] = []
    dialog.export_clicked.connect(lambda: fired.append("export"))
    dialog.delete_clicked.connect(lambda: fired.append("delete"))
    dialog.clear_clicked.connect(lambda: fired.append("clear"))
    dialog.close_clicked.connect(lambda: fired.append("close"))
    dialog.set_export_enabled(True)
    dialog.set_delete_enabled(True)
    dialog.set_clear_enabled(True)
    _button(dialog, "exportButton").click()
    _button(dialog, "deleteButton").click()
    _button(dialog, "clearButton").click()
    _button(dialog, "closeButton").click()
    assert fired == ["export", "delete", "clear", "close"]


def _row(row_id: int) -> tuple[int, str, str, str, str, str, str]:
    return (row_id, "start", "active", "cost", "no", "name", "client")


def test_select_all_toggles_only_visible_rows(dialog: HistoryDialog) -> None:
    dialog.set_rows([_row(1), _row(2)])
    select_all = dialog.findChild(QCheckBox, "selectAll")
    assert select_all is not None and select_all.isEnabled()
    select_all.click()
    assert dialog.checked_ids() == (1, 2)
    assert select_all.checkState() == Qt.CheckState.Checked
    item = _table(dialog).item(0, 0)
    assert item is not None
    item.setCheckState(Qt.CheckState.Unchecked)
    assert dialog.checked_ids() == (2,)
    assert select_all.checkState() == Qt.CheckState.PartiallyChecked
    select_all.click()
    assert dialog.checked_ids() == (1, 2)
    select_all.click()
    assert dialog.checked_ids() == ()
    assert select_all.checkState() == Qt.CheckState.Unchecked


def test_click_toggles_row_checkbox(dialog: HistoryDialog) -> None:
    dialog.set_rows([_row(1)])
    dialog.show()
    table = _table(dialog)
    item = table.item(0, 0)
    assert item is not None
    QTest.mouseClick(
        table.viewport(), Qt.MouseButton.LeftButton, pos=table.visualItemRect(item).center()
    )
    assert dialog.checked_ids() == (1,)


def test_set_rows_keeps_checks_for_rows_that_stay(dialog: HistoryDialog) -> None:
    dialog.set_rows([_row(1), _row(2)])
    item = _table(dialog).item(1, 0)
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked)
    dialog.set_rows([_row(2), _row(3)])
    assert dialog.checked_ids() == (2,)
    kept = _table(dialog).item(0, 0)
    added = _table(dialog).item(1, 0)
    assert kept is not None and added is not None
    assert kept.checkState() == Qt.CheckState.Checked
    assert kept.data(Qt.ItemDataRole.UserRole) == 2
    assert added.checkState() == Qt.CheckState.Unchecked


def test_escape_emits_close(dialog: HistoryDialog) -> None:
    fired: list[str] = []
    dialog.close_clicked.connect(lambda: fired.append("close"))
    dialog.export_clicked.connect(lambda: fired.append("export"))
    dialog.show()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert fired == ["close"]


def test_summary_card_hides_figures_until_a_client_is_shown(dialog: HistoryDialog) -> None:
    assert _label(dialog, "summaryCaption").text() == t("history.summary.pick")
    assert _label(dialog, "summaryCostCaption").text() == t("history.summary.cost")
    assert _label(dialog, "summaryCost").isHidden()
    assert _label(dialog, "summaryTime").isHidden()
    project = dialog.findChild(QComboBox, "summaryProject")
    assert project is not None
    assert not project.isEnabled()
    assert project.itemText(0) == t("history.filter.project.all")

    dialog.show_summary("15.00 ₽", "01:00:50", "Ivan")
    assert not _label(dialog, "summaryCost").isHidden()
    assert _label(dialog, "summaryCost").text() == "15.00 ₽"
    assert _label(dialog, "summaryTime").text() == "01:00:50"
    assert _label(dialog, "summaryCaption").text() == t(
        "history.summary.caption", client="Ivan", period=dialog.period_label()
    )
    dialog.show_summary("10.00 ₽", "01:00:00", "Ivan", "7", "Kitchen")
    assert _label(dialog, "summaryCaption").text() == t(
        "history.summary.caption.project",
        client="Ivan",
        number="7 Kitchen",
        period=dialog.period_label(),
    )


def test_set_period_orders_bounds(dialog: HistoryDialog) -> None:
    dialog.set_period(QDate(2026, 10, 21), QDate(2026, 10, 1))
    start, end = dialog.period_bounds()
    assert datetime.fromtimestamp(start) == datetime(2026, 10, 1)
    assert datetime.fromtimestamp(end) == datetime(2026, 10, 21, 23, 59, 59)


def test_calendar_commits_range_on_the_second_click(dialog: HistoryDialog) -> None:
    fired: list[int] = []
    dialog.period_changed.connect(lambda: fired.append(1))
    calendar = dialog.findChild(RangeCalendar, "periodCalendar")
    assert calendar is not None
    calendar.pick(QDate(2026, 5, 2))
    assert fired == []
    calendar.pick(QDate(2026, 5, 10))
    assert fired == [1]
    start, end = dialog.period_bounds()
    assert datetime.fromtimestamp(start) == datetime(2026, 5, 2)
    assert datetime.fromtimestamp(end) == datetime(2026, 5, 10, 23, 59, 59)
    calendar.pick(QDate(2026, 5, 20))
    assert fired == [1]
    calendar.pick(QDate(2026, 5, 4))
    start, end = dialog.period_bounds()
    assert datetime.fromtimestamp(start).day == 4
    assert datetime.fromtimestamp(end).day == 20


def test_client_enables_only_that_clients_projects(dialog: HistoryDialog) -> None:
    dialog.set_client_choices(["Anna", "Ivan"])
    dialog.set_project_choices([("9", "Hall"), ("12", "")])
    client = dialog.findChild(QComboBox, "summaryClient")
    project = dialog.findChild(QComboBox, "summaryProject")
    assert client is not None and project is not None
    client.setCurrentIndex(client.findData("Ivan"))
    assert project.isEnabled()
    dialog.set_project_choices([("7", "Kitchen"), ("12", "Wardrobe")])
    assert project.currentData() == ""
    assert project.itemText(project.findData("7")) == "7 · Kitchen"
    project.setCurrentIndex(project.findData("12"))
    dialog.set_project_choices([("12", "Wardrobe"), ("3", "Desk")])
    assert project.currentData() == "12"
    assert dialog.selected_project_name() == "Wardrobe"


def test_place_near_widget(dialog: HistoryDialog, widget: TimerWidget) -> None:
    dialog.place_near(widget.frameGeometry())
    dialog.show()
    assert dialog.isVisible()
