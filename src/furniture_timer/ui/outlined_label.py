"""QLabel that paints its text with a dark outline, legible on any backdrop."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QLabel, QWidget


class OutlinedLabel(QLabel):
    """Single-line, horizontally centered text: outline stroke under a solid fill."""

    def __init__(
        self, parent: QWidget | None = None, outline: QColor | None = None, width: float = 4.0
    ) -> None:
        super().__init__(parent)
        self._outline_pen = QPen(
            outline if outline is not None else QColor(0, 0, 0),
            width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        text = self.text()
        if not text:
            return
        font = self.font()
        metrics = QFontMetricsF(font)
        rect = self.contentsRect()
        origin = QPointF(
            rect.center().x() + 0.5 - metrics.horizontalAdvance(text) / 2,
            rect.center().y() + 0.5 + (metrics.ascent() - metrics.descent()) / 2,
        )
        path = QPainterPath()
        path.addText(origin, font, text)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.strokePath(path, self._outline_pen)
        painter.fillPath(path, self.palette().color(QPalette.ColorRole.WindowText))
