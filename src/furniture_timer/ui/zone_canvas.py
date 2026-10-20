"""Screenshot canvas: draw and select active (green) and interrupt (red) zones."""

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from furniture_timer.screen_zones import ZoneRole

MIN_ZONE_PX = 16
_DISPLAY_WIDTH = 680
_ACTIVE = QColor("#1B5E20")
_INTERRUPT = QColor("#E53935")
_SELECTED = QColor("#ffffff")

ZonePaint = tuple[str, ZoneRole, int, int, int, int]


class ZoneCanvas(QWidget):
    """Image-space rectangles. The dialog owns the zone list."""

    zone_drawn = Signal(int, int, int, int)
    zone_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("zoneCanvas")
        self.setMouseTracking(True)
        self._image = QImage()
        self._zones: tuple[ZonePaint, ...] = ()
        self._selected: str | None = None
        self._tool = ZoneRole.ACTIVE
        self._scale = 1.0
        self._origin: tuple[int, int] | None = None
        self._current: tuple[int, int] | None = None

    def set_scene(
        self,
        image: QImage,
        zones: Sequence[ZonePaint],
        selected: str | None,
        tool: ZoneRole,
    ) -> None:
        self._image = image
        self._zones = tuple(zones)
        self._selected = selected
        self._tool = tool
        self._origin = None
        self._current = None
        if image.isNull() or image.width() < 1:
            self._scale = 1.0
            self.setFixedSize(1, 1)
        else:
            self._scale = 1.0 if image.width() <= _DISPLAY_WIDTH else _DISPLAY_WIDTH / image.width()
            self.setFixedSize(
                max(1, int(image.width() * self._scale)),
                max(1, int(image.height() * self._scale)),
            )
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))
        if not self._image.isNull():
            painter.drawImage(self.rect(), self._image)
        for zone_id, role, x, y, width, height in self._zones:
            self._paint_rect(painter, role, x, y, width, height, zone_id == self._selected)
        if self._origin is not None and self._current is not None:
            rect = _normalized(self._origin, self._current)
            if rect is not None:
                self._paint_rect(painter, self._tool, *rect, selected=True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._image.isNull():
            self._origin = self._image_point(event.position())
            self._current = self._origin
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin is None:
            super().mouseMoveEvent(event)
            return
        self._current = self._image_point(event.position())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            super().mouseReleaseEvent(event)
            return
        end = self._image_point(event.position())
        rect = _normalized(self._origin, end)
        self._origin = None
        self._current = None
        self.update()
        if rect is not None and rect[2] >= MIN_ZONE_PX and rect[3] >= MIN_ZONE_PX:
            self.zone_drawn.emit(*rect)
        else:
            hit = self._hit(end)
            if hit is not None:
                self.zone_selected.emit(hit)
        event.accept()

    def _paint_rect(
        self,
        painter: QPainter,
        role: ZoneRole,
        x: int,
        y: int,
        width: int,
        height: int,
        selected: bool,
    ) -> None:
        color = QColor(_ACTIVE if role is ZoneRole.ACTIVE else _INTERRUPT)
        fill = QColor(color)
        fill.setAlpha(110)
        display = QRect(
            int(x * self._scale),
            int(y * self._scale),
            max(1, int(width * self._scale)),
            max(1, int(height * self._scale)),
        )
        painter.fillRect(display, fill)
        pen = QPen(_SELECTED if selected else color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(display.adjusted(0, 0, -1, -1))

    def _image_point(self, pos: QPointF) -> tuple[int, int]:
        if self._image.isNull():
            return 0, 0
        x = int(pos.x() / self._scale)
        y = int(pos.y() / self._scale)
        return (
            min(max(0, x), self._image.width() - 1),
            min(max(0, y), self._image.height() - 1),
        )

    def _hit(self, point: tuple[int, int]) -> str | None:
        px, py = point
        for zone_id, _role, x, y, width, height in reversed(self._zones):
            if x <= px < x + width and y <= py < y + height:
                return zone_id
        return None


def _normalized(
    origin: tuple[int, int], end: tuple[int, int]
) -> tuple[int, int, int, int] | None:
    left, right = sorted((origin[0], end[0]))
    top, bottom = sorted((origin[1], end[1]))
    width = right - left
    height = bottom - top
    if width < 1 or height < 1:
        return None
    return left, top, width, height
