"""Turn Qt screen grabs into grayscale buffers the matcher can search."""

from PySide6.QtCore import QBuffer, QIODevice, QPoint
from PySide6.QtGui import QCursor, QGuiApplication, QImage
from PySide6.QtWidgets import QApplication

from furniture_timer.screen_zones import GrayBuffer


def grab_screens() -> list[GrayBuffer]:
    """One grayscale buffer per monitor. Empty when the platform cannot grab."""
    app = QApplication.instance() or QGuiApplication.instance()
    if app is None:
        return []
    buffers: list[GrayBuffer] = []
    for screen in app.screens():
        image = screen.grabWindow(0).toImage()
        if image.isNull() or image.width() < 1 or image.height() < 1:
            continue
        buffers.append(gray_buffer_from_image(image))
    return buffers


def gray_buffer_from_image(image: QImage) -> GrayBuffer:
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    width = gray.width()
    height = gray.height()
    if width < 1 or height < 1:
        raise ValueError("empty image")
    line = gray.bytesPerLine()
    raw = memoryview(gray.constBits()).cast("B")
    if line == width:
        pixels = bytes(raw[: width * height])
    else:
        packed = bytearray(width * height)
        for y in range(height):
            start = y * line
            packed[y * width : (y + 1) * width] = raw[start : start + width]
        pixels = bytes(packed)
    return GrayBuffer(width, height, pixels)


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ValueError("could not encode png")
    if not image.save(buffer, "PNG"):
        raise ValueError("could not encode png")
    return bytes(buffer.data())


def grab_cursor_screen() -> QImage | None:
    """Grab the monitor under the cursor, or the primary monitor."""
    screen = QGuiApplication.screenAt(_cursor_pos()) or QGuiApplication.primaryScreen()
    if screen is None:
        return None
    grab = screen.grabWindow(0)
    image = grab.toImage()
    if image.isNull() or image.width() < 1 or image.height() < 1:
        return None
    # Detach before `grab` is released; otherwise the pixels can change.
    return image.copy(0, 0, image.width(), image.height())


def _cursor_pos() -> QPoint:
    return QCursor.pos()
