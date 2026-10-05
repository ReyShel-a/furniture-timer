"""Frameless settings panel: rate, currency, idle threshold. No business logic."""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from furniture_timer.i18n import t
from furniture_timer.ui.placement import place_near as _place_near
from furniture_timer.ui.theme import apply_theme, background_color
from furniture_timer.ui.widget import WIDGET_WIDTH


class SettingsDialog(QWidget):
    save_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setFixedWidth(WIDGET_WIDTH)
        self.setWindowTitle(t("settings.dialog.title"))
        self._background = background_color()

        self._title = QLabel(t("settings.dialog.title"), self)
        self._title.setObjectName("settingsTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._rate_edit = self._make_edit("rateEdit")
        self._currency_edit = self._make_edit("currencyEdit")
        self._idle_edit = self._make_edit("idleEdit")
        self._rate_edit.returnPressed.connect(self.save_clicked)
        self._currency_edit.returnPressed.connect(self.save_clicked)
        self._idle_edit.returnPressed.connect(self.save_clicked)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.addRow(self._make_label("rateLabel", t("settings.field.rate")), self._rate_edit)
        form.addRow(
            self._make_label("currencyLabel", t("settings.field.currency")),
            self._currency_edit,
        )
        form.addRow(
            self._make_label("idleLabel", t("settings.field.idle_threshold")),
            self._idle_edit,
        )

        self._error = QLabel(self)
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)
        self._error.hide()

        self._save = self._make_button("saveButton", t("settings.btn.save"))
        self._cancel = self._make_button("cancelButton", t("settings.btn.cancel"))
        self._save.setDefault(True)
        self._save.clicked.connect(self.save_clicked)
        self._cancel.clicked.connect(self.cancel_clicked)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(self._save, 1)
        buttons.addWidget(self._cancel, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        root.addWidget(self._title)
        root.addLayout(form)
        root.addWidget(self._error)
        root.addLayout(buttons)
        apply_theme(self)

    def set_values(self, rate: float, currency: str, idle_threshold_sec: int) -> None:
        self._rate_edit.setText(str(rate))
        self._currency_edit.setText(currency)
        self._idle_edit.setText(str(idle_threshold_sec))

    def values(self) -> tuple[str, str, str]:
        return (
            self._rate_edit.text(),
            self._currency_edit.text(),
            self._idle_edit.text(),
        )

    def show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()

    def clear_error(self) -> None:
        self._error.clear()
        self._error.hide()

    def place_near(self, widget_geo: QRect) -> None:
        _place_near(self, widget_geo)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._background)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _make_label(self, name: str, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName(name)
        return label

    def _make_edit(self, name: str) -> QLineEdit:
        edit = QLineEdit(self)
        edit.setObjectName(name)
        return edit

    def _make_button(self, name: str, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button
