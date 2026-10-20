"""Screen-zone profile: screenshots, rectangles, and grayscale crops on disk."""

import json
import logging
import re
import struct
import zlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)

PROFILE_VERSION = 1
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


class ZoneRole(Enum):
    ACTIVE = "active"
    INTERRUPT = "interrupt"


@dataclass(frozen=True)
class GrayBuffer:
    """8-bit grayscale image, row-major, one byte per pixel."""

    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("image size must be positive")
        if len(self.pixels) != self.width * self.height:
            raise ValueError("pixel count does not match size")


@dataclass(frozen=True)
class SourceShot:
    id: str
    width: int
    height: int
    png: bytes


@dataclass(frozen=True)
class Zone:
    id: str
    source_id: str
    role: ZoneRole
    x: int
    y: int
    width: int
    height: int
    crop: GrayBuffer


@dataclass(frozen=True)
class ScreenProfile:
    sources: tuple[SourceShot, ...] = ()
    zones: tuple[Zone, ...] = ()

    @staticmethod
    def empty() -> "ScreenProfile":
        return ScreenProfile()


def has_active_zone(profile: ScreenProfile) -> bool:
    return any(zone.role is ZoneRole.ACTIVE for zone in profile.zones)


def load_profile(root: Path) -> ScreenProfile:
    """Read a profile. A missing or unreadable file is an empty profile."""
    path = root / "profile.json"
    if not path.is_file():
        return ScreenProfile.empty()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != PROFILE_VERSION:
            raise ValueError("unsupported profile version")
        sources = _load_sources(root, payload.get("sources"))
        known = {source.id for source in sources}
        zones = _load_zones(root, payload.get("zones"), known)
    except Exception:
        log.warning("Could not read screen profile at %s", path, exc_info=True)
        return ScreenProfile.empty()
    return ScreenProfile(sources=tuple(sources), zones=tuple(zones))


def save_profile(root: Path, profile: ScreenProfile) -> None:
    """Write the profile, replacing previous crops and screenshots."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir(exist_ok=True)
    (root / "crops").mkdir(exist_ok=True)
    keep: set[Path] = set()
    source_meta: list[dict[str, object]] = []
    for source in profile.sources:
        _check_id(source.id)
        path = _child(root, "sources", f"{source.id}.png")
        path.write_bytes(source.png)
        keep.add(path)
        source_meta.append(
            {
                "id": source.id,
                "file": f"sources/{source.id}.png",
                "width": source.width,
                "height": source.height,
            }
        )
    zone_meta: list[dict[str, object]] = []
    for zone in profile.zones:
        _check_id(zone.id)
        _check_id(zone.source_id)
        path = _child(root, "crops", f"{zone.id}.png")
        path.write_bytes(write_gray_png(zone.crop))
        keep.add(path)
        zone_meta.append(
            {
                "id": zone.id,
                "source_id": zone.source_id,
                "role": zone.role.value,
                "x": zone.x,
                "y": zone.y,
                "width": zone.width,
                "height": zone.height,
                "crop": f"crops/{zone.id}.png",
            }
        )
    document = {"version": PROFILE_VERSION, "sources": source_meta, "zones": zone_meta}
    (root / "profile.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    for folder in (root / "sources", root / "crops"):
        for child in folder.iterdir():
            if child.is_file() and child.resolve() not in keep:
                child.unlink()


def write_gray_png(image: GrayBuffer) -> bytes:
    """Encode an 8-bit grayscale PNG (filter None, no interlace)."""
    raw = bytearray()
    row = image.width
    for y in range(image.height):
        raw.append(0)
        raw.extend(image.pixels[y * row : (y + 1) * row])
    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, 0, 0, 0, 0)
    return (
        _PNG_SIG
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def read_gray_png(data: bytes) -> GrayBuffer:
    """Decode a grayscale PNG written by write_gray_png."""
    if not data.startswith(_PNG_SIG):
        raise ValueError("not a png")
    pos = len(_PNG_SIG)
    width: int | None = None
    height: int | None = None
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        pos += 4
        tag = data[pos : pos + 4]
        pos += 4
        chunk = data[pos : pos + length]
        pos += length + 4
        if tag == b"IHDR":
            width, height, depth, color, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            if (depth, color, comp, filt, inter) != (8, 0, 0, 0, 0):
                raise ValueError("unsupported png")
        elif tag == b"IDAT":
            idat.extend(chunk)
        elif tag == b"IEND":
            break
    if width is None or height is None:
        raise ValueError("missing ihdr")
    raw = zlib.decompress(bytes(idat))
    stride = width + 1
    if len(raw) != height * stride:
        raise ValueError("bad idat size")
    pixels = bytearray(width * height)
    for y in range(height):
        start = y * stride
        if raw[start] != 0:
            raise ValueError("unsupported filter")
        pixels[y * width : (y + 1) * width] = raw[start + 1 : start + 1 + width]
    return GrayBuffer(width, height, bytes(pixels))


def _load_sources(root: Path, raw: object) -> list[SourceShot]:
    sources: list[SourceShot] = []
    if not isinstance(raw, list):
        raise ValueError("sources must be a list")
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            source_id = _check_id(item.get("id"))
            width = _positive_int(item.get("width"))
            height = _positive_int(item.get("height"))
            png = _child(root, "sources", f"{source_id}.png").read_bytes()
        except (OSError, TypeError, ValueError):
            log.warning("Skipping unreadable screenshot %r", item.get("id") if isinstance(item, dict) else item)
            continue
        sources.append(SourceShot(source_id, width, height, png))
    return sources


def _load_zones(root: Path, raw: object, known: set[str]) -> list[Zone]:
    zones: list[Zone] = []
    if not isinstance(raw, list):
        raise ValueError("zones must be a list")
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            zone_id = _check_id(item.get("id"))
            source_id = _check_id(item.get("source_id"))
            if source_id not in known:
                raise ValueError("unknown source")
            role = ZoneRole(item.get("role"))
            crop = read_gray_png(_child(root, "crops", f"{zone_id}.png").read_bytes())
            zone = Zone(
                zone_id,
                source_id,
                role,
                _non_negative_int(item.get("x")),
                _non_negative_int(item.get("y")),
                _positive_int(item.get("width")),
                _positive_int(item.get("height")),
                crop,
            )
        except (OSError, TypeError, ValueError):
            log.warning("Skipping unreadable zone %r", item.get("id") if isinstance(item, dict) else item)
            continue
        zones.append(zone)
    return zones


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _check_id(value: object) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid id: {value!r}")
    return value


def _positive_int(value: object) -> int:
    number = _non_negative_int(value)
    if number < 1:
        raise ValueError("expected a positive int")
    return number


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("expected a non-negative int")
    return value


def _child(root: Path, folder: str, name: str) -> Path:
    path = (root / folder / name).resolve()
    if root.resolve() not in path.parents:
        raise ValueError("path escapes profile dir")
    return path
