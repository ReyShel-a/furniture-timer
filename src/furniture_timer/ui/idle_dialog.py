"""Non-blocking idle alert: Keep / Discard idle / Resume. No business logic."""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from furniture_timer.i18n import t
from furniture_timer.ui.theme import apply_theme, background_color
from furniture_timer.ui.widget import WIDGET_WIDTH

_GAP_PX = 8


class IdleDialog(QWidget):
    keep_clicked = Signal()
    resume_clicked = Signal()
    discard_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("IdleDialog")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedWidth(WIDGET_WIDTH)
        self.setWindowTitle(t("idle.dialog.title"))
        self._background = background_color()
        self._prompt = False

        self._message = QLabel(self)
        self._message.setObjectName("idleMessage")
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._keep = self._make_button(
            "keepButton", t("idle.btn.keep"), t("idle.btn.keep.tooltip")
        )
        self._discard = self._make_button(
            "discardButton", t("idle.btn.discard"), t("idle.btn.discard.tooltip")
        )
        self._resume = self._make_button(
            "resumeButton", t("idle.btn.resume"), t("idle.btn.resume.tooltip")
        )
        self._keep.clicked.connect(self.keep_clicked)
        self._discard.clicked.connect(self.discard_clicked)
        self._resume.clicked.connect(self.resume_clicked)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self._keep, 1)
        buttons.addWidget(self._discard, 1)
        buttons.addWidget(self._resume, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        root.addWidget(self._message)
        root.addLayout(buttons)
        apply_theme(self)

    @property
    def is_prompt(self) -> bool:
        return self._prompt

    def show_alert(self, duration: str) -> None:
        self._prompt = False
        self._set_message(duration)
        self.show()

    def show_prompt(self, duration: str) -> None:
        self._prompt = True
        self._set_message(duration)
        self.show()

    def update_duration(self, duration: str) -> None:
        self._set_message(duration)

    def is_on_screen(self) -> bool:
        if not self.isVisible() or self.isMinimized():
            return False
        geo = self.frameGeometry()
        return any(geo.intersects(screen.availableGeometry()) for screen in QGuiApplication.screens())

    def place_near(self, widget_geo: QRect) -> None:
        self.adjustSize()
        size = self.frameGeometry().size()
        screens = QGuiApplication.screens()
        on_a_screen = any(widget_geo.intersects(s.availableGeometry()) for s in screens)
        primary = QGuiApplication.primaryScreen()
        if primary is None:
            return
        available = primary.availableGeometry()
        if not on_a_screen:
            self.move(available.right() - size.width(), available.bottom() - size.height())
            return
        screen = QGuiApplication.screenAt(widget_geo.center()) or primary
        available = screen.availableGeometry()
        x = widget_geo.x()
        y_below = widget_geo.bottom() + _GAP_PX
        if y_below + size.height() <= available.bottom():
            y = y_below
        else:
            y = widget_geo.top() - _GAP_PX - size.height()
        x = min(max(x, available.left()), available.right() - size.width())
        y = min(max(y, available.top()), available.bottom() - size.height())
        self.move(x, y)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._background)

    def _set_message(self, duration: str) -> None:
        key = "idle.prompt.message" if self._prompt else "idle.dialog.message"
        self._message.setText(t(key, duration=duration))

    def _make_button(self, name: str, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        return button
