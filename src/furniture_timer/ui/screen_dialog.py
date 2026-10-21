"""Framed editor for screen-zone pause and resume. No timer decisions."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from furniture_timer.i18n import t
from furniture_timer.screen_zones import GrayBuffer, ScreenProfile, ZoneRole
from furniture_timer.ui.screen_draft import ScreenDraft
from furniture_timer.ui.screen_grab import grab_cursor_screen
from furniture_timer.ui.theme import BG, DANGER, DARK_QSS, FG
from furniture_timer.ui.zone_canvas import ZoneCanvas

_EXTRA_QSS = f"""
QDialog {{ background-color: {BG}; color: {FG}; }}
QCheckBox, QRadioButton {{ color: {FG}; font-size: 10pt; }}
QListWidget {{
    color: {FG};
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    font-size: 10pt;
}}
QScrollArea {{ background: {BG}; border: none; }}
"""


class ScreenDialog(QDialog):
    save_clicked = Signal()
    cancel_clicked = Signal()
    check_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenDialog")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setModal(False)
        self.setMinimumSize(760, 520)
        self.setWindowTitle(t("screen.dialog.title"))
        self.setStyleSheet(DARK_QSS + _EXTRA_QSS)
        self._draft = ScreenDraft()
        self._build()

    def load_from(self, profile: ScreenProfile, enabled: bool) -> None:
        self._draft.load(profile)
        self._enable.setChecked(enabled)
        self.show_status("")
        self._sync_view()

    def enabled(self) -> bool:
        return self._enable.isChecked()

    def has_active_zone(self) -> bool:
        return self._draft.has_active_zone()

    def add_image(self, image: QImage, *, replace: bool = False) -> str:
        source_id = self._draft.add_image(image, replace=replace)
        self.show_status("")
        self._sync_view()
        return source_id

    def add_zone(
        self, x: int, y: int, width: int, height: int, role: ZoneRole | None = None
    ) -> None:
        self._draft.add_zone(x, y, width, height, role if role is not None else self._tool_role())
        self._sync_view()

    def build_profile(self) -> ScreenProfile:
        return self._draft.build_profile()

    def draft_needles(self) -> list[tuple[str, ZoneRole, GrayBuffer]]:
        return self._draft.needles()

    def show_status(self, text: str, *, error: bool = False) -> None:
        self._status.setText(text)
        color = DANGER if error else FG
        self._status.setStyleSheet(f"color: {color}; font-size: 9pt;")

    def retranslate(self) -> None:
        self.setWindowTitle(t("screen.dialog.title"))
        self._title.setText(t("screen.dialog.title"))
        self._hint.setText(t("screen.hint"))
        self._enable.setText(t("screen.enable"))
        self._upload.setText(t("screen.btn.upload"))
        self._capture.setText(t("screen.btn.capture"))
        self._active.setText(t("screen.role.active"))
        self._interrupt.setText(t("screen.role.interrupt"))
        self._delete_button.setText(t("screen.btn.delete"))
        self._check.setText(t("screen.btn.check"))
        self._save.setText(t("settings.btn.save"))
        self._cancel.setText(t("settings.btn.cancel"))
        self._sync_view()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _build(self) -> None:
        self._title = QLabel(t("screen.dialog.title"), self)
        self._title.setObjectName("screenTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint = QLabel(t("screen.hint"), self)
        self._hint.setObjectName("screenHint")
        self._hint.setWordWrap(True)
        self._enable = QCheckBox(t("screen.enable"), self)
        self._enable.setObjectName("enableCheck")
        self._upload = self._button("uploadButton", t("screen.btn.upload"))
        self._capture = self._button("captureButton", t("screen.btn.capture"))
        self._active = QRadioButton(t("screen.role.active"), self)
        self._active.setObjectName("activeRadio")
        self._active.setChecked(True)
        self._interrupt = QRadioButton(t("screen.role.interrupt"), self)
        self._interrupt.setObjectName("interruptRadio")
        self._delete_button = self._button("deleteButton", t("screen.btn.delete"))
        self._check = self._button("checkButton", t("screen.btn.check"))
        self._source = QComboBox(self)
        self._source.setObjectName("sourceCombo")
        self._canvas = ZoneCanvas(self)
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("canvasScroll")
        self._scroll.setWidget(self._canvas)
        self._scroll.setMinimumHeight(280)
        self._list = QListWidget(self)
        self._list.setObjectName("zoneList")
        self._list.setFixedWidth(180)
        self._status = QLabel(self)
        self._status.setObjectName("statusLabel")
        self._status.setWordWrap(True)
        self._save = self._button("saveButton", t("settings.btn.save"))
        self._cancel = self._button("cancelButton", t("settings.btn.cancel"))
        self._upload.clicked.connect(self._upload_file)
        self._capture.clicked.connect(self._capture_screen)
        self._delete_button.clicked.connect(self._delete_selected)
        self._check.clicked.connect(self.check_clicked)
        self._save.clicked.connect(self.save_clicked)
        self._cancel.clicked.connect(self.cancel_clicked)
        self._active.toggled.connect(lambda _checked: self._sync_canvas())
        self._source.currentIndexChanged.connect(self._on_source)
        self._list.currentItemChanged.connect(lambda _cur, _prev: self._on_list())
        self._canvas.zone_drawn.connect(self.add_zone)
        self._canvas.zone_selected.connect(self._select_zone)
        tools = QHBoxLayout()
        for widget in (
            self._upload,
            self._capture,
            self._active,
            self._interrupt,
            self._delete_button,
            self._check,
        ):
            tools.addWidget(widget)
        body = QHBoxLayout()
        body.addWidget(self._scroll, 1)
        body.addWidget(self._list)
        buttons = QHBoxLayout()
        buttons.addWidget(self._save, 1)
        buttons.addWidget(self._cancel, 1)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)
        for widget in (self._title, self._hint, self._enable):
            root.addWidget(widget)
        root.addLayout(tools)
        root.addWidget(self._source)
        root.addLayout(body, 1)
        root.addWidget(self._status)
        root.addLayout(buttons)

    def _upload_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self, t("screen.btn.upload"), "", t("screen.file.filter")
        )
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            self.show_status(t("screen.error.image"), error=True)
            return
        self.add_image(image)

    def _capture_screen(self) -> None:
        self.hide()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        image = grab_cursor_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        if image is None:
            self.show_status(t("screen.error.capture"), error=True)
            return
        self.add_image(image, replace=True)

    def _delete_selected(self) -> None:
        self._draft.delete_selected()
        self._sync_view()

    def _select_zone(self, zone_id: str) -> None:
        self._draft.select_zone(zone_id)
        self._sync_view()

    def _on_source(self, index: int) -> None:
        if self._source.signalsBlocked():
            return
        source_id = self._source.itemData(index)
        self._draft.select_source(None if source_id is None else str(source_id))
        self._sync_view()

    def _on_list(self) -> None:
        if self._list.signalsBlocked():
            return
        item = self._list.currentItem()
        if item is None:
            self._draft.selected = None
        else:
            self._draft.select_zone(str(item.data(Qt.ItemDataRole.UserRole)))
        self._sync_canvas()

    def _sync_view(self) -> None:
        self._source.blockSignals(True)
        self._source.clear()
        current = 0
        for index, source in enumerate(self._draft.sources):
            self._source.addItem(t("screen.source.item", index=index + 1), source.id)
            if source.id == self._draft.source_id:
                current = index
        if self._draft.sources:
            self._source.setCurrentIndex(current)
            self._draft.source_id = self._draft.sources[current].id
        self._source.blockSignals(False)
        self._list.blockSignals(True)
        self._list.clear()
        selected_row = -1
        for zone_id, label in self._draft.list_rows():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, zone_id)
            self._list.addItem(item)
            if zone_id == self._draft.selected:
                selected_row = self._list.count() - 1
        if selected_row >= 0:
            self._list.setCurrentRow(selected_row)
        self._list.blockSignals(False)
        self._sync_canvas()

    def _sync_canvas(self) -> None:
        self._canvas.set_scene(
            self._draft.current_image(),
            self._draft.canvas_zones(),
            self._draft.selected,
            self._tool_role(),
        )

    def _tool_role(self) -> ZoneRole:
        if self._interrupt.isChecked():
            return ZoneRole.INTERRUPT
        return ZoneRole.ACTIVE

    def _button(self, name: str, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button
