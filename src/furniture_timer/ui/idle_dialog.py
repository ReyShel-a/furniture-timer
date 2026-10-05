"""Non-blocking idle alert: Keep / Discard idle / Resume. No business logic."""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from furniture_timer.i18n import t
from furniture_timer.ui.placement import place_near as _place_near
from furniture_timer.ui.theme import apply_theme, background_color
from furniture_timer.ui.widget import WIDGET_WIDTH


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
        self._duration: str | None = None

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
        _place_near(self, widget_geo)

    def retranslate(self) -> None:
        self.setWindowTitle(t("idle.dialog.title"))
        self._keep.setText(t("idle.btn.keep"))
        self._keep.setToolTip(t("idle.btn.keep.tooltip"))
        self._discard.setText(t("idle.btn.discard"))
        self._discard.setToolTip(t("idle.btn.discard.tooltip"))
        self._resume.setText(t("idle.btn.resume"))
        self._resume.setToolTip(t("idle.btn.resume.tooltip"))
        if self._duration is not None:
            self._set_message(self._duration)
        self.adjustSize()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._background)

    def _set_message(self, duration: str) -> None:
        self._duration = duration
        key = "idle.prompt.message" if self._prompt else "idle.dialog.message"
        self._message.setText(t(key, duration=duration))

    def _make_button(self, name: str, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        return button
