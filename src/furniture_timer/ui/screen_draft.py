"""Editable screenshots and rectangles behind the zone editor."""

import uuid
from dataclasses import dataclass

from PySide6.QtGui import QImage

from furniture_timer.i18n import t
from furniture_timer.screen_zones import (
    GrayBuffer,
    ScreenProfile,
    SourceShot,
    Zone,
    ZoneRole,
)
from furniture_timer.ui.screen_grab import gray_buffer_from_image, png_bytes
from furniture_timer.ui.zone_canvas import MIN_ZONE_PX

_ROLE_KEY = {
    ZoneRole.ACTIVE: "screen.role.active",
    ZoneRole.INTERRUPT: "screen.role.interrupt",
}


@dataclass
class DraftSource:
    id: str
    image: QImage


@dataclass
class DraftZone:
    id: str
    source_id: str
    role: ZoneRole
    x: int
    y: int
    width: int
    height: int


class ScreenDraft:
    def __init__(self) -> None:
        self.sources: list[DraftSource] = []
        self.zones: list[DraftZone] = []
        self.source_id: str | None = None
        self.selected: str | None = None

    def load(self, profile: ScreenProfile) -> None:
        self.sources.clear()
        self.zones.clear()
        self.selected = None
        known: set[str] = set()
        for source in profile.sources:
            image = QImage()
            image.loadFromData(source.png)
            if image.isNull():
                continue
            self.sources.append(DraftSource(source.id, image))
            known.add(source.id)
        for zone in profile.zones:
            if zone.source_id not in known:
                continue
            self.zones.append(
                DraftZone(
                    zone.id,
                    zone.source_id,
                    zone.role,
                    zone.x,
                    zone.y,
                    zone.width,
                    zone.height,
                )
            )
        self.source_id = self.sources[0].id if self.sources else None

    def has_active_zone(self) -> bool:
        return any(zone.role is ZoneRole.ACTIVE for zone in self.zones)

    def add_image(self, image: QImage, *, replace: bool = False) -> str:
        """Store a screenshot. replace=True overwrites the selected shot."""
        stored = image.copy(0, 0, image.width(), image.height())
        current = self.current_source() if replace else None
        if current is None:
            source_id = uuid.uuid4().hex
            self.sources.append(DraftSource(source_id, stored))
            self.source_id = source_id
            self.selected = None
            return source_id
        current.image = stored
        self.zones = [
            zone
            for zone in self.zones
            if zone.source_id != current.id or _fits(stored, zone)
        ]
        if not any(zone.id == self.selected for zone in self.zones):
            self.selected = None
        return current.id

    def add_zone(
        self, x: int, y: int, width: int, height: int, role: ZoneRole
    ) -> None:
        source = self.current_source()
        if source is None or width < MIN_ZONE_PX or height < MIN_ZONE_PX:
            return
        if x < 0 or y < 0 or x + width > source.image.width() or y + height > source.image.height():
            return
        zone_id = uuid.uuid4().hex
        self.zones.append(DraftZone(zone_id, source.id, role, x, y, width, height))
        self.selected = zone_id

    def delete_selected(self) -> None:
        if self.selected is None:
            return
        self.zones = [zone for zone in self.zones if zone.id != self.selected]
        self.selected = None

    def select_source(self, source_id: str | None) -> None:
        if source_id == self.source_id:
            return
        self.source_id = source_id
        self.selected = None

    def select_zone(self, zone_id: str) -> None:
        self.selected = zone_id

    def current_source(self) -> DraftSource | None:
        for source in self.sources:
            if source.id == self.source_id:
                return source
        return None

    def current_image(self) -> QImage:
        source = self.current_source()
        if source is None:
            return QImage()
        return source.image

    def canvas_zones(self) -> tuple[tuple[str, ZoneRole, int, int, int, int], ...]:
        return tuple(
            (zone.id, zone.role, zone.x, zone.y, zone.width, zone.height)
            for zone in self.zones
            if zone.source_id == self.source_id
        )

    def list_rows(self) -> list[tuple[str, str]]:
        return [
            (zone.id, _zone_label(zone))
            for zone in self.zones
            if zone.source_id == self.source_id
        ]

    def build_profile(self) -> ScreenProfile:
        sources = tuple(
            SourceShot(source.id, source.image.width(), source.image.height(), png_bytes(source.image))
            for source in self.sources
        )
        zones: list[Zone] = []
        for zone in self.zones:
            crop = _crop(self.sources, zone)
            if crop is None:
                continue
            zones.append(
                Zone(
                    zone.id,
                    zone.source_id,
                    zone.role,
                    zone.x,
                    zone.y,
                    zone.width,
                    zone.height,
                    crop,
                )
            )
        return ScreenProfile(sources, tuple(zones))

    def needles(self) -> list[tuple[str, ZoneRole, GrayBuffer]]:
        found: list[tuple[str, ZoneRole, GrayBuffer]] = []
        for zone in self.zones:
            crop = _crop(self.sources, zone)
            if crop is not None:
                found.append((_zone_label(zone), zone.role, crop))
        return found


def _zone_label(zone: DraftZone) -> str:
    return t(
        "screen.zone.item",
        role=t(_ROLE_KEY[zone.role]),
        width=zone.width,
        height=zone.height,
    )


def _crop(sources: list[DraftSource], zone: DraftZone) -> GrayBuffer | None:
    source = next((item for item in sources if item.id == zone.source_id), None)
    if source is None:
        return None
    image = source.image
    if not _fits(image, zone):
        return None
    return gray_buffer_from_image(image.copy(zone.x, zone.y, zone.width, zone.height))


def _fits(image: QImage, zone: DraftZone) -> bool:
    return (
        zone.width >= 1
        and zone.height >= 1
        and zone.x >= 0
        and zone.y >= 0
        and zone.x + zone.width <= image.width()
        and zone.y + zone.height <= image.height()
    )
