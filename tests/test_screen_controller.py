"""Screen sampling pauses and resumes an open session only."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from furniture_timer import db
from furniture_timer.screen_zones import (
    GrayBuffer,
    ScreenProfile,
    SourceShot,
    Zone,
    ZoneRole,
    has_active_zone,
    load_profile,
    save_profile,
)
from furniture_timer.settings import Settings
from furniture_timer.timer_model import TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.screen_controller import SAMPLE_INTERVAL_MS, ScreenController
from furniture_timer.ui.screen_dialog import ScreenDialog
from furniture_timer.ui.screen_grab import gray_buffer_from_image
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget


class Frames:
    def __init__(self, image: GrayBuffer) -> None:
        self.images = [image]

    def __call__(self) -> list[GrayBuffer]:
        return list(self.images)


def _solid(width: int, height: int, value: int) -> GrayBuffer:
    return GrayBuffer(width, height, bytes([value]) * (width * height))


def _paste(base: GrayBuffer, patch: GrayBuffer, x: int, y: int) -> GrayBuffer:
    pixels = bytearray(base.pixels)
    for row in range(patch.height):
        start = (y + row) * base.width + x
        src = row * patch.width
        pixels[start : start + patch.width] = patch.pixels[src : src + patch.width]
    return GrayBuffer(base.width, base.height, bytes(pixels))


def _active_profile(crop: GrayBuffer) -> ScreenProfile:
    return ScreenProfile(
        sources=(SourceShot("shot1", crop.width, crop.height, b"png"),),
        zones=(Zone("zone1", "shot1", ZoneRole.ACTIVE, 0, 0, crop.width, crop.height, crop),),
    )


@pytest.fixture
def widget(qapp: QApplication) -> Iterator[TimerWidget]:
    window = TimerWidget()
    window.show()
    yield window
    window.close()
    window.deleteLater()


def test_sample_pauses_resumes_and_does_not_start(
    qapp: QApplication, widget: TimerWidget, tmp_path: Path
) -> None:
    crop = GrayBuffer(8, 8, bytes((index * 17) % 255 for index in range(64)))
    blank = _solid(32, 24, 0)
    frames = Frames(blank)
    conn = db.connect(tmp_path / "db.sqlite")
    settings = Settings(conn)
    settings.screen_auto_enabled = True
    root = tmp_path / "profile"
    save_profile(root, _active_profile(crop))
    model = TimerModel()
    timer = TimerController(model, widget)
    dialog = ScreenDialog(widget)
    screen = ScreenController(
        model,
        widget,
        SettingsDialog(widget),
        dialog,
        settings,
        timer,
        profile_dir=root,
        grabber=frames,
        parent=widget,
    )

    assert screen.sample_interval_ms == SAMPLE_INTERVAL_MS == 30_000
    assert not screen.is_polling

    timer.toggle_start_pause()
    assert model.state is TimerState.RUNNING
    assert screen.is_polling
    assert "Screen: active" in widget.toolTip()

    screen.sample(block=True)
    assert model.state is TimerState.PAUSED
    assert "Screen: paused" in widget.toolTip()

    frames.images = [_paste(blank, crop, 4, 6)]
    screen.sample(block=True)
    assert model.state is TimerState.RUNNING

    widget.stop_clicked.emit()
    assert model.state is TimerState.IDLE
    assert not screen.is_polling
    screen.sample(block=True)
    assert model.state is TimerState.IDLE

    timer.deleteLater()
    dialog.deleteLater()
    conn.close()


def test_manual_pause_holds_until_the_user_resumes(
    qapp: QApplication, widget: TimerWidget, tmp_path: Path
) -> None:
    crop = GrayBuffer(8, 8, bytes((index * 17) % 255 for index in range(64)))
    frames = Frames(_paste(_solid(32, 24, 0), crop, 4, 6))
    conn = db.connect(tmp_path / "db.sqlite")
    settings = Settings(conn)
    settings.screen_auto_enabled = True
    root = tmp_path / "profile"
    save_profile(root, _active_profile(crop))
    model = TimerModel()
    timer = TimerController(model, widget)
    screen = ScreenController(
        model,
        widget,
        SettingsDialog(widget),
        ScreenDialog(widget),
        settings,
        timer,
        profile_dir=root,
        grabber=frames,
        parent=widget,
    )

    timer.toggle_start_pause()
    timer.toggle_start_pause()
    assert model.state is TimerState.PAUSED
    assert "Screen: manual pause" in widget.toolTip()

    screen.sample(block=True)
    assert model.state is TimerState.PAUSED

    timer.toggle_start_pause()
    assert model.state is TimerState.RUNNING
    conn.close()


def test_system_idle_auto_pause_is_left_alone(
    qapp: QApplication, widget: TimerWidget, tmp_path: Path
) -> None:
    crop = GrayBuffer(8, 8, bytes(range(64)))
    frames = Frames(_solid(16, 16, 9))
    conn = db.connect(tmp_path / "db.sqlite")
    settings = Settings(conn)
    settings.screen_auto_enabled = True
    root = tmp_path / "profile"
    save_profile(root, _active_profile(crop))
    model = TimerModel()
    timer = TimerController(model, widget)
    screen = ScreenController(
        model,
        widget,
        SettingsDialog(widget),
        ScreenDialog(widget),
        settings,
        timer,
        profile_dir=root,
        grabber=frames,
        parent=widget,
    )

    timer.toggle_start_pause()
    model.auto_pause(5)
    timer.refresh()
    assert model.state is TimerState.AUTO_PAUSED

    frames.images[0] = _paste(_solid(16, 16, 9), crop, 0, 0)
    screen.sample(block=True)
    assert model.state is TimerState.AUTO_PAUSED
    conn.close()


def test_failed_grab_does_not_change_the_timer(
    qapp: QApplication, widget: TimerWidget, tmp_path: Path
) -> None:
    crop = GrayBuffer(8, 8, bytes(range(64)))
    conn = db.connect(tmp_path / "db.sqlite")
    settings = Settings(conn)
    settings.screen_auto_enabled = True
    root = tmp_path / "profile"
    save_profile(root, _active_profile(crop))
    model = TimerModel()
    timer = TimerController(model, widget)

    def _fail() -> list[GrayBuffer]:
        raise RuntimeError("grab failed")

    screen = ScreenController(
        model,
        widget,
        SettingsDialog(widget),
        ScreenDialog(widget),
        settings,
        timer,
        profile_dir=root,
        grabber=_fail,
        parent=widget,
    )
    timer.toggle_start_pause()
    screen.sample(block=True)
    assert model.state is TimerState.RUNNING
    conn.close()


def test_editor_save_requires_an_active_zone_then_persists(
    qapp: QApplication, widget: TimerWidget, tmp_path: Path
) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    settings = Settings(conn)
    root = tmp_path / "profile"
    model = TimerModel()
    timer = TimerController(model, widget)
    settings_dialog = SettingsDialog(widget)
    dialog = ScreenDialog(widget)
    frames = Frames(_solid(48, 40, 0))
    screen = ScreenController(
        model,
        widget,
        settings_dialog,
        dialog,
        settings,
        timer,
        profile_dir=root,
        grabber=frames,
        parent=widget,
    )
    enable = dialog.findChild(QCheckBox, "enableCheck")
    status = dialog.findChild(QLabel, "statusLabel")
    assert enable is not None and status is not None

    enable.setChecked(True)
    dialog.save_clicked.emit()
    assert settings.screen_auto_enabled is False
    assert status.text()

    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(QColor(12, 24, 36))
    dialog.add_image(image)
    dialog.add_zone(2, 2, 16, 16, ZoneRole.ACTIVE)
    needle = dialog.draft_needles()[0][2]
    frames.images = [_paste(_solid(48, 40, 0), needle, 2, 2)]
    dialog.check_clicked.emit()
    assert "Decision: active" in status.text()
    dialog.save_clicked.emit()

    assert settings.screen_auto_enabled is True
    assert not dialog.isVisible()
    loaded = load_profile(root)
    assert has_active_zone(loaded)
    assert loaded.zones[0].crop == gray_buffer_from_image(image.copy(2, 2, 16, 16))

    screen.open_editor()
    assert dialog.isVisible()
    assert dialog.enabled() is True
    button = settings_dialog.findChild(QPushButton, "screenButton")
    assert button is not None
    dialog.hide()
    button.click()
    assert dialog.isVisible()
    conn.close()
