"""Frameless always-on-top timer widget (passive view, no business logic)."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QMoveEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from furniture_timer.formatting import format_clock, format_hms
from furniture_timer.i18n import t
from furniture_timer.settings import DEFAULT_CURRENCY, DEFAULT_HOURLY_RATE
from furniture_timer.timer_model import TimerState
from furniture_timer.ui.outlined_label import OutlinedLabel
from furniture_timer.ui.theme import apply_theme, background_color

WIDGET_WIDTH = 260
WIDGET_HEIGHT = 150
GLYPH_BUTTON_WIDTH = 28

_START_PAUSE_KEYS: dict[TimerState, str] = {
    TimerState.IDLE: "btn.start",
    TimerState.RUNNING: "btn.pause",
    TimerState.PAUSED: "btn.resume",
    TimerState.AUTO_PAUSED: "btn.resume",
}


class TimerWidget(QWidget):
    start_pause_clicked = Signal()
    stop_clicked = Signal()
    settings_clicked = Signal()
    close_clicked = Signal()
    moved = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setObjectName("TimerWidget")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.setWindowTitle(t("app.title"))
        self._drag_offset: QPoint | None = None
        self._background = background_color()
        self._state = TimerState.IDLE
        self._rate = DEFAULT_HOURLY_RATE
        self._cost = 0.0
        self._currency = DEFAULT_CURRENCY
        self._start_ts: int | None = None

        self._time_label = self._make_label("timeLabel")
        self._price_label = self._make_label("priceLabel")
        self._start_pause_button = self._make_button("startPauseButton")
        self._stop_button = self._make_button("stopButton", text=t("btn.stop"))
        self._settings_button = self._make_button(
            "settingsButton", text=t("btn.settings.glyph"), tooltip=t("btn.settings")
        )
        self._close_button = self._make_button(
            "closeButton", text=t("btn.close.glyph"), tooltip=t("btn.close")
        )
        self._settings_button.setFixedWidth(GLYPH_BUTTON_WIDTH)
        self._close_button.setFixedWidth(GLYPH_BUTTON_WIDTH)

        self._start_pause_button.clicked.connect(self.start_pause_clicked)
        self._stop_button.clicked.connect(self.stop_clicked)
        self._settings_button.clicked.connect(self.settings_clicked)
        self._close_button.clicked.connect(self.close_clicked)

        self._build_layout()
        apply_theme(self)

        self.show_time(format_hms(0))
        self.show_price(DEFAULT_HOURLY_RATE, 0.0, DEFAULT_CURRENCY)
        self.show_state(TimerState.IDLE)
        self.show_session_start(None)

    def show_time(self, text: str) -> None:
        self._time_label.setText(text)

    def show_price(self, rate: float, cost: float, currency: str) -> None:
        self._rate = rate
        self._cost = cost
        self._currency = currency
        self._price_label.setText(
            t("widget.price_line", rate=rate, cost=cost, currency=currency)
        )

    def show_state(self, state: TimerState) -> None:
        self._state = state
        self._start_pause_button.setText(t(_START_PAUSE_KEYS[state]))
        self._stop_button.setEnabled(state is not TimerState.IDLE)

    def show_session_start(self, ts: int | None) -> None:
        self._start_ts = ts
        if ts is None:
            self.setToolTip(t("widget.tooltip.not_started"))
        else:
            self.setToolTip(t("widget.tooltip.started", time=format_clock(ts)))

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.title"))
        self._stop_button.setText(t("btn.stop"))
        self._settings_button.setText(t("btn.settings.glyph"))
        self._settings_button.setToolTip(t("btn.settings"))
        self._close_button.setText(t("btn.close.glyph"))
        self._close_button.setToolTip(t("btn.close"))
        self.show_price(self._rate, self._cost, self._currency)
        self.show_state(self._state)
        self.show_session_start(self._start_ts)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._background)

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self.moved.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        handle = self.windowHandle()
        if handle is None or not handle.startSystemMove():
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is None or not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        self.move(event.globalPosition().toPoint() - self._drag_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def _make_label(self, name: str) -> QLabel:
        label = OutlinedLabel(self)
        label.setObjectName(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _make_button(self, name: str, text: str = "", tooltip: str = "") -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            button.setToolTip(tooltip)
        return button

    def _build_layout(self) -> None:
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self._start_pause_button, 1)
        buttons.addWidget(self._stop_button, 1)
        buttons.addWidget(self._settings_button)
        buttons.addWidget(self._close_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(4)
        root.addWidget(self._time_label)
        root.addWidget(self._price_label)
        root.addLayout(buttons)
