from furniture_timer.screen_match import MATCH_THRESHOLD, ScreenSignal, best_score, judge
from furniture_timer.screen_zones import GrayBuffer, ZoneRole


def _solid(width: int, height: int, value: int) -> GrayBuffer:
    return GrayBuffer(width, height, bytes([value]) * (width * height))


def _paste(base: GrayBuffer, patch: GrayBuffer, x: int, y: int) -> GrayBuffer:
    pixels = bytearray(base.pixels)
    for row in range(patch.height):
        start = (y + row) * base.width + x
        src = row * patch.width
        pixels[start : start + patch.width] = patch.pixels[src : src + patch.width]
    return GrayBuffer(base.width, base.height, bytes(pixels))


def test_exact_crop_scores_one() -> None:
    needle = GrayBuffer(8, 6, bytes((index * 19) % 255 for index in range(48)))
    haystack = _paste(_solid(30, 20, 4), needle, 7, 5)

    assert best_score(haystack, needle) == 1.0


def test_unrelated_image_misses_threshold() -> None:
    score = best_score(_solid(20, 20, 0), _solid(8, 8, 255))

    assert score < MATCH_THRESHOLD


def test_needle_larger_than_screen_scores_zero() -> None:
    assert best_score(_solid(4, 4, 1), _solid(5, 5, 1)) == 0.0


def test_downscaled_aligned_crop_still_matches() -> None:
    needle = GrayBuffer(16, 8, bytes((index * 13) % 250 + 1 for index in range(128)))
    haystack = _paste(_solid(480, 32, 3), needle, 8, 4)

    assert best_score(haystack, needle) == 1.0


def test_large_screen_finds_an_offset_crop_quickly() -> None:
    needle = GrayBuffer(40, 30, bytes((index * 17) % 251 + 1 for index in range(1200)))
    haystack = _paste(_solid(640, 360, 8), needle, 13, 7)

    assert best_score(haystack, needle) == 1.0
    assert best_score(_solid(640, 360, 8), needle) < MATCH_THRESHOLD


def test_interrupt_zone_wins_over_active_hit() -> None:
    scores = [(ZoneRole.ACTIVE, 1.0), (ZoneRole.INTERRUPT, MATCH_THRESHOLD)]

    assert judge(scores) == ScreenSignal.INTERRUPT


def test_active_when_every_green_zone_hits_and_red_does_not() -> None:
    scores = [(ZoneRole.ACTIVE, 0.95), (ZoneRole.ACTIVE, 0.91), (ZoneRole.INTERRUPT, 0.2)]

    assert judge(scores) == ScreenSignal.ACTIVE


def test_absent_without_a_full_active_match() -> None:
    assert judge([(ZoneRole.ACTIVE, 0.5)]) == ScreenSignal.ABSENT
    assert judge([]) == ScreenSignal.ABSENT
