"""One-month calendar that selects an inclusive date range with two clicks."""

from PySide6.QtCore import QDate, QLocale, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QCalendarWidget, QLabel, QVBoxLayout, QWidget

from furniture_timer.i18n import language, t
from furniture_timer.ui.theme import ACCENT, FG, MUTED, ON_COLOR, SURFACE, SURFACE_HOVER

_DATE_FORMAT = "d MMM yyyy"


class HighlightCalendar(QCalendarWidget):
    """Month grid that paints the chosen range instead of a single selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._start = QDate()
        self._end = QDate()
        self.setObjectName("periodGrid")
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setNavigationBarVisible(True)
        self.setFixedHeight(200)
        self._apply_palette()

    def set_highlight(self, start: QDate, end: QDate) -> None:
        if start.isValid() and end.isValid() and start > end:
            start, end = end, start
        self._start = start
        self._end = end
        self.updateCells()

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate) -> None:
        painter.save()
        in_range = (
            self._start.isValid()
            and self._end.isValid()
            and self._start <= date <= self._end
        )
        is_edge = date == self._start or date == self._end
        other_month = date.month() != self.monthShown() or date.year() != self.yearShown()
        if is_edge:
            painter.fillRect(rect, QColor(ACCENT))
            color = QColor(ON_COLOR)
        elif in_range:
            painter.fillRect(rect, QColor(SURFACE_HOVER))
            color = QColor(FG)
        else:
            painter.fillRect(rect, QColor(SURFACE))
            color = QColor(MUTED if other_month else FG)
        if date == QDate.currentDate() and not is_edge:
            painter.setPen(QPen(QColor(ACCENT)))
            painter.drawRect(rect.adjusted(2, 2, -3, -3))
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
        painter.restore()

    def _apply_palette(self) -> None:
        palette = self.palette()
        surface = QColor(SURFACE)
        text = QColor(FG)
        palette.setColor(QPalette.ColorRole.Window, surface)
        palette.setColor(QPalette.ColorRole.WindowText, text)
        palette.setColor(QPalette.ColorRole.Base, surface)
        palette.setColor(QPalette.ColorRole.Text, text)
        palette.setColor(QPalette.ColorRole.Button, surface)
        palette.setColor(QPalette.ColorRole.ButtonText, text)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(ON_COLOR))
        self.setPalette(palette)


class RangeCalendar(QWidget):
    """Committed range plus a pending first click that does not reload history yet."""

    range_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("periodCalendar")
        today = QDate.currentDate()
        self._start = QDate(today.year(), today.month(), 1)
        self._end = today
        self._pending: QDate | None = None

        self._label = QLabel(self)
        self._label.setObjectName("periodLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._grid = HighlightCalendar(self)
        self._grid.set_highlight(self._start, self._end)
        self._grid.setCurrentPage(today.year(), today.month())
        self._grid.clicked.connect(self.pick)
        self.apply_language()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._label)
        layout.addWidget(self._grid)

    def bounds(self) -> tuple[QDate, QDate]:
        """Committed inclusive dates. A pending first click does not change them."""
        return (self._start, self._end)

    def period_text(self) -> str:
        return t(
            "history.period.range",
            start=self._format(self._start),
            end=self._format(self._end),
        )

    def set_period(self, start: QDate, end: QDate) -> None:
        if start > end:
            start, end = end, start
        self._pending = None
        self._start = start
        self._end = end
        self._grid.set_highlight(start, end)
        self._grid.setCurrentPage(start.year(), start.month())
        self._refresh_label()
        self.range_changed.emit()

    def pick(self, day: QDate) -> None:
        """First click anchors the range; the second click commits it."""
        if self._pending is None:
            self._pending = day
            self._grid.set_highlight(day, day)
            self._refresh_label()
            return
        start, end = self._pending, day
        self._pending = None
        if start > end:
            start, end = end, start
        self._start = start
        self._end = end
        self._grid.set_highlight(start, end)
        self._refresh_label()
        self.range_changed.emit()

    def apply_language(self) -> None:
        if language() == "ru":
            locale = QLocale(QLocale.Language.Russian)
        else:
            locale = QLocale(QLocale.Language.English)
        self._grid.setLocale(locale)
        self._refresh_label()

    def _refresh_label(self) -> None:
        if self._pending is not None:
            self._label.setText(self._format(self._pending))
            return
        self._label.setText(self.period_text())

    def _format(self, day: QDate) -> str:
        return self._grid.locale().toString(day, _DATE_FORMAT)
