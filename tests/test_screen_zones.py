import json
from pathlib import Path

from furniture_timer.screen_zones import (
    GrayBuffer,
    ScreenProfile,
    SourceShot,
    Zone,
    ZoneRole,
    load_profile,
    save_profile,
    write_gray_png,
    read_gray_png,
)


def _profile() -> ScreenProfile:
    crop = GrayBuffer(4, 3, bytes(range(12)))
    return ScreenProfile(
        sources=(SourceShot("shot1", 20, 10, b"not-a-real-png"),),
        zones=(
            Zone("zone1", "shot1", ZoneRole.ACTIVE, 1, 2, 4, 3, crop),
            Zone("zone2", "shot1", ZoneRole.INTERRUPT, 0, 0, 4, 3, crop),
        ),
    )


def test_gray_png_roundtrip() -> None:
    image = GrayBuffer(5, 2, bytes((index * 40) % 256 for index in range(10)))

    assert read_gray_png(write_gray_png(image)) == image


def test_profile_roundtrip_replaces_old_files(tmp_path: Path) -> None:
    root = tmp_path / "screen_profile"
    save_profile(root, _profile())
    stale = root / "crops" / "gone.png"
    stale.write_bytes(b"old")

    kept = ScreenProfile(
        sources=_profile().sources,
        zones=(_profile().zones[0],),
    )
    save_profile(root, kept)
    loaded = load_profile(root)

    assert loaded.sources[0].png == b"not-a-real-png"
    assert loaded.zones == (kept.zones[0],)
    assert not stale.exists()


def test_missing_profile_is_empty(tmp_path: Path) -> None:
    assert load_profile(tmp_path / "missing") == ScreenProfile.empty()


def test_corrupt_profile_is_empty(tmp_path: Path, caplog) -> None:
    root = tmp_path / "screen_profile"
    root.mkdir()
    (root / "profile.json").write_text("{", encoding="utf-8")

    assert load_profile(root) == ScreenProfile.empty()
    assert "Could not read screen profile" in caplog.text


def test_zone_with_missing_crop_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "screen_profile"
    save_profile(root, _profile())
    (root / "crops" / "zone2.png").unlink()

    loaded = load_profile(root)

    assert [zone.id for zone in loaded.zones] == ["zone1"]


def test_unknown_version_is_empty(tmp_path: Path) -> None:
    root = tmp_path / "screen_profile"
    save_profile(root, _profile())
    document = json.loads((root / "profile.json").read_text(encoding="utf-8"))
    document["version"] = 99
    (root / "profile.json").write_text(json.dumps(document), encoding="utf-8")

    assert load_profile(root) == ScreenProfile.empty()
