from collections.abc import Iterator
from datetime import datetime

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton

from furniture_timer.i18n import _STRINGS, t
from furniture_timer.timer_model import TimerState
from furniture_timer.ui.outlined_label import OutlinedLabel
from furniture_timer.ui.widget import WIDGET_HEIGHT, WIDGET_WIDTH, TimerWidget

USED_KEYS = [
    "app.title",
    "btn.start",
    "btn.pause",
    "btn.resume",
    "btn.stop",
    "btn.settings",
    "btn.settings.glyph",
    "btn.close",
    "btn.close.glyph",
    "widget.price_line",
    "widget.tooltip.started",
    "widget.tooltip.not_started",
    "widget.field.project_number",
    "widget.field.project_name",
    "widget.field.client",
    "idle.dialog.title",
    "idle.dialog.message",
    "idle.prompt.message",
    "idle.btn.keep",
    "idle.btn.resume",
    "idle.btn.discard",
    "idle.btn.keep.tooltip",
    "idle.btn.resume.tooltip",
    "idle.btn.discard.tooltip",
    "settings.dialog.title",
    "settings.field.rate",
    "settings.field.currency",
    "settings.field.idle_threshold",
    "settings.field.language",
    "settings.lang.en",
    "settings.lang.ru",
    "settings.btn.save",
    "settings.btn.cancel",
    "settings.btn.history",
    "settings.error.rate",
    "settings.error.currency",
    "settings.error.idle_threshold",
    "settings.error.language",
    "history.dialog.title",
    "history.col.start",
    "history.col.active",
    "history.col.cost",
    "history.col.project_number",
    "history.col.project_name",
    "history.col.client",
    "history.empty",
    "history.btn.export",
    "history.btn.clear",
    "history.btn.close",
    "history.export.title",
    "history.export.filter",
    "history.error.write",
    "history.error.clear",
    "history.error.summary",
    "history.summary.pick",
    "history.summary.total",
    "history.period.from",
    "history.period.to",
    "tray.action.show",
    "tray.action.quit",
]


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    w = TimerWidget()
    w.show()
    yield w
    w.close()
    w.deleteLater()


def _button(widget: TimerWidget, name: str) -> QPushButton:
    button = widget.findChild(QPushButton, name)
    assert button is not None, name
    return button


def _label(widget: TimerWidget, name: str) -> QLabel:
    label = widget.findChild(QLabel, name)
    assert label is not None, name
    return label


def test_window_flags(widget: TimerWidget) -> None:
    flags = widget.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert (flags & Qt.WindowType.Tool) == Qt.WindowType.Tool


def test_fixed_size(widget: TimerWidget) -> None:
    assert widget.minimumSize() == widget.maximumSize() == QSize(WIDGET_WIDTH, WIDGET_HEIGHT)


def test_children_have_object_names(widget: TimerWidget) -> None:
    assert widget.objectName() == "TimerWidget"
    for name in ("timeLabel", "priceLabel"):
        _label(widget, name)
    for name in ("startPauseButton", "stopButton", "settingsButton", "closeButton"):
        _button(widget, name)


def test_initial_view(widget: TimerWidget) -> None:
    assert _label(widget, "timeLabel").text() == "00:00:00"
    assert _label(widget, "priceLabel").text() == "0.00 ₽/h  ·  0.00 ₽"
    assert _button(widget, "startPauseButton").text() == "Start"
    assert not _button(widget, "stopButton").isEnabled()
    assert widget.toolTip() == "No active session"
    assert widget.windowTitle() == "Furniture Timer"


@pytest.mark.parametrize(
    ("state", "text", "stop_enabled"),
    [
        (TimerState.IDLE, "Start", False),
        (TimerState.RUNNING, "Pause", True),
        (TimerState.PAUSED, "Resume", True),
        (TimerState.AUTO_PAUSED, "Resume", True),
    ],
)
def test_show_state(
    widget: TimerWidget, state: TimerState, text: str, stop_enabled: bool
) -> None:
    widget.show_state(state)
    assert _button(widget, "startPauseButton").text() == text
    assert _button(widget, "stopButton").isEnabled() is stop_enabled


@pytest.mark.parametrize(
    ("button_name", "signal_name"),
    [
        ("startPauseButton", "start_pause_clicked"),
        ("stopButton", "stop_clicked"),
        ("settingsButton", "settings_clicked"),
        ("closeButton", "close_clicked"),
    ],
)
def test_button_emits_only_its_signal(
    widget: TimerWidget, button_name: str, signal_name: str
) -> None:
    widget.show_state(TimerState.RUNNING)
    fired: list[str] = []
    for name in ("start_pause_clicked", "stop_clicked", "settings_clicked", "close_clicked"):
        getattr(widget, name).connect(lambda name=name: fired.append(name))

    _button(widget, button_name).click()

    assert fired == [signal_name]


def test_show_time(widget: TimerWidget) -> None:
    widget.show_time("01:02:03")
    assert _label(widget, "timeLabel").text() == "01:02:03"


def test_show_price(widget: TimerWidget) -> None:
    widget.show_price(12.5, 3.4, "₽")
    assert _label(widget, "priceLabel").text() == "12.50 ₽/h  ·  3.40 ₽"


def test_session_start_tooltip(widget: TimerWidget) -> None:
    ts = int(datetime(2026, 10, 5, 14, 30).timestamp())
    widget.show_session_start(ts)
    assert widget.toolTip() == "Session started at 14:30"

    widget.show_session_start(None)
    assert widget.toolTip() == "No active session"


def test_glyph_buttons_have_tooltips(widget: TimerWidget) -> None:
    assert _button(widget, "settingsButton").text() == "⚙"
    assert _button(widget, "settingsButton").toolTip() == "Settings"
    assert _button(widget, "closeButton").text() == "×"
    assert _button(widget, "closeButton").toolTip() == "Close"


def test_dark_theme_applied(widget: TimerWidget) -> None:
    qss = widget.styleSheet()
    for color in ("#e0e0e0", "#4caf50", "#e53935"):
        assert color in qss
    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_background_is_dark_and_translucent(widget: TimerWidget) -> None:
    pixel = widget.grab().toImage().pixelColor(2, 2)
    assert pixel.alpha() == 191
    for channel in (pixel.red(), pixel.green(), pixel.blue()):
        assert abs(channel - 30) <= 1


def test_labels_are_outlined(widget: TimerWidget) -> None:
    for name in ("timeLabel", "priceLabel"):
        assert isinstance(_label(widget, name), OutlinedLabel)


def _send_mouse(
    widget: TimerWidget, kind: QEvent.Type, local: QPoint, buttons: Qt.MouseButton
) -> None:
    global_pos = QPointF(widget.pos() + local)
    event = QMouseEvent(
        kind,
        QPointF(local),
        global_pos,
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def test_fallback_drag_moves_window(widget: TimerWidget) -> None:
    widget.move(100, 100)
    start = widget.pos()
    left = Qt.MouseButton.LeftButton
    no_buttons = Qt.MouseButton.NoButton

    _send_mouse(widget, QEvent.Type.MouseButtonPress, QPoint(10, 10), left)
    _send_mouse(widget, QEvent.Type.MouseMove, QPoint(60, 40), left)
    _send_mouse(widget, QEvent.Type.MouseButtonRelease, QPoint(60, 40), no_buttons)

    assert widget.pos() == start + QPoint(50, 30)


def test_moved_signal_emits_on_move(widget: TimerWidget) -> None:
    fired: list[int] = []
    widget.moved.connect(lambda: fired.append(1))
    widget.move(120, 80)
    assert fired == [1]


@pytest.mark.parametrize("key", USED_KEYS)
def test_used_i18n_keys_exist(key: str) -> None:
    assert key in _STRINGS["en"]
    assert t(
        key, rate=0.0, cost=0.0, currency="₽", time="00:00", duration="00:00:00"
    ) != key


def test_no_unused_i18n_keys() -> None:
    assert set(_STRINGS["en"]) <= set(USED_KEYS)
