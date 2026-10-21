"""Capturing again replaces the screenshot the zones already belong to."""

from pathlib import Path

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QPushButton

from furniture_timer.screen_zones import ZoneRole, load_profile, save_profile
from furniture_timer.ui.screen_dialog import ScreenDialog
from furniture_timer.ui.screen_grab import gray_buffer_from_image


def _solid(width: int, height: int, color: QColor) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(color)
    return image


def _rgb(png: bytes) -> tuple[int, int, int]:
    image = QImage()
    assert image.loadFromData(png)
    color = image.pixelColor(0, 0)
    return color.red(), color.green(), color.blue()


def test_capture_replaces_screenshot_and_keeps_zones(
    qapp: QApplication, monkeypatch, tmp_path: Path
) -> None:
    dialog = ScreenDialog()
    old = _solid(40, 30, QColor(10, 20, 30))
    new = _solid(40, 30, QColor(200, 10, 10))
    dialog.add_image(old)
    dialog.add_zone(2, 2, 16, 16, ZoneRole.ACTIVE)
    root = tmp_path / "profile"
    save_profile(root, dialog.build_profile())
    dialog.load_from(load_profile(root), False)

    monkeypatch.setattr(
        "furniture_timer.ui.screen_dialog.grab_cursor_screen",
        lambda: new,
    )
    capture = dialog.findChild(QPushButton, "captureButton")
    assert capture is not None
    capture.click()
    dialog.add_zone(4, 4, 18, 16, ZoneRole.INTERRUPT)
    save_profile(root, dialog.build_profile())

    loaded = load_profile(root)
    assert len(loaded.sources) == 1
    assert len(list((root / "sources").glob("*.png"))) == 1
    assert _rgb(loaded.sources[0].png) == (200, 10, 10)
    assert [(zone.role, zone.x, zone.y, zone.width, zone.height) for zone in loaded.zones] == [
        (ZoneRole.ACTIVE, 2, 2, 16, 16),
        (ZoneRole.INTERRUPT, 4, 4, 18, 16),
    ]
    assert loaded.zones[0].crop == gray_buffer_from_image(new.copy(2, 2, 16, 16))

    dialog.load_from(loaded, False)
    assert len(dialog.build_profile().sources) == 1
    assert _rgb(dialog.build_profile().sources[0].png) == (200, 10, 10)
    dialog.deleteLater()


def test_replace_drops_zones_outside_the_new_image(qapp: QApplication) -> None:
    fresh = ScreenDialog()
    fresh.add_image(_solid(8, 8, QColor(1, 1, 1)), replace=True)
    assert len(fresh.build_profile().sources) == 1
    fresh.deleteLater()

    dialog = ScreenDialog()
    dialog.add_image(_solid(40, 30, QColor(1, 2, 3)))
    dialog.add_zone(2, 2, 16, 16, ZoneRole.ACTIVE)
    dialog.add_image(_solid(12, 12, QColor(9, 8, 7)), replace=True)

    profile = dialog.build_profile()
    assert len(profile.sources) == 1
    assert profile.sources[0].width == 12
    assert profile.zones == ()
    dialog.deleteLater()
