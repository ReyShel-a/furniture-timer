"""Find zone crops on a screen grab. Qt-free so it can run in unit tests."""

from collections.abc import Sequence

from furniture_timer.screen_zones import GrayBuffer, ZoneRole

MATCH_THRESHOLD = 0.90
_COARSE_STEP = 8
_PROBE_CELLS = 8


class ScreenSignal:
    """What the current monitors mean for an open session."""

    ACTIVE = "active"
    INTERRUPT = "interrupt"
    ABSENT = "absent"


def best_score(haystack: GrayBuffer, needle: GrayBuffer) -> float:
    """Best similarity in 0..1. 1 is an exact copy. 0 if the needle cannot fit.

    Large screens are reduced to a coarse grid first. Searching every pixel of
    a full-HD grab on the UI thread froze the timer for about 14 seconds.
    """
    if needle.width > haystack.width or needle.height > haystack.height:
        return 0.0
    x_span = haystack.width - needle.width + 1
    y_span = haystack.height - needle.height + 1
    if x_span * y_span <= 20_000:
        return _score_at(haystack, needle, 1)
    factor = 8
    while factor > 1 and (needle.width // factor < 2 or needle.height // factor < 2):
        factor //= 2
    small_hay = _point_sample(haystack, factor)
    small_needle = _point_sample(needle, factor)
    if (
        small_needle.width > small_hay.width
        or small_needle.height > small_hay.height
        or small_needle.width < 1
        or small_needle.height < 1
    ):
        return _score_at(haystack, needle, _COARSE_STEP)
    sx, sy, diff = _locate(small_hay, small_needle, 1)
    if diff == 0.0 and factor == 1:
        return 1.0
    origin_x = min(sx * factor, haystack.width - needle.width)
    origin_y = min(sy * factor, haystack.height - needle.height)
    _x, _y, fine = _refine(haystack, needle, _probes(needle), origin_x, origin_y, factor)
    return 1.0 - (fine / 255.0)


def _score_at(haystack: GrayBuffer, needle: GrayBuffer, step: int) -> float:
    _x, _y, diff = _locate(haystack, needle, step)
    return 1.0 - (diff / 255.0)


def _locate(
    haystack: GrayBuffer, needle: GrayBuffer, step: int
) -> tuple[int, int, float]:
    probes = _probes(needle)
    x, y, diff = _search(haystack, needle, probes, step)
    if step > 1 and diff != 0.0:
        x, y, diff = _refine(haystack, needle, probes, x, y, step)
    return x, y, diff


def _point_sample(image: GrayBuffer, factor: int) -> GrayBuffer:
    if factor <= 1:
        return image
    width = image.width // factor
    height = image.height // factor
    if width < 1 or height < 1:
        return image
    src = image.pixels
    stride = image.width
    half = factor // 2
    out = bytearray(width * height)
    for y in range(height):
        row = (y * factor + half) * stride
        base = y * width
        for x in range(width):
            out[base + x] = src[row + x * factor + half]
    return GrayBuffer(width, height, bytes(out))


def judge(
    scores: Sequence[tuple[ZoneRole, float]],
    threshold: float = MATCH_THRESHOLD,
) -> str:
    """Interrupt wins over active. Active requires every green zone to hit."""
    saw_active = False
    active_ok = True
    for role, score in scores:
        if role is ZoneRole.INTERRUPT and score >= threshold:
            return ScreenSignal.INTERRUPT
        if role is ZoneRole.ACTIVE:
            saw_active = True
            if score < threshold:
                active_ok = False
    if saw_active and active_ok:
        return ScreenSignal.ACTIVE
    return ScreenSignal.ABSENT


def score_zones(
    zones: Sequence[tuple[ZoneRole, GrayBuffer]],
    grabs: Sequence[GrayBuffer],
) -> str:
    """Best score of each zone across grabs, then the active/interrupt decision."""
    scored: list[tuple[ZoneRole, float]] = []
    for role, crop in zones:
        best = 0.0
        for grab in grabs:
            best = max(best, best_score(grab, crop))
        scored.append((role, best))
    return judge(scored)


def _probes(needle: GrayBuffer) -> tuple[tuple[int, int], ...]:
    """Evenly spaced sample points. An exact copy still scores 1 at these pixels."""
    cells_x = min(_PROBE_CELLS, needle.width)
    cells_y = min(_PROBE_CELLS, needle.height)
    xs = [min(needle.width - 1, (index * needle.width) // cells_x) for index in range(cells_x)]
    ys = [min(needle.height - 1, (index * needle.height) // cells_y) for index in range(cells_y)]
    return tuple((x, y) for y in ys for x in xs)


def _search(
    haystack: GrayBuffer,
    needle: GrayBuffer,
    probes: tuple[tuple[int, int], ...],
    step: int,
) -> tuple[int, int, float]:
    best_total = 255 * len(probes) + 1
    best_x = 0
    best_y = 0
    y_limit = haystack.height - needle.height
    x_limit = haystack.width - needle.width
    y = 0
    while y <= y_limit:
        x = 0
        while x <= x_limit:
            total = _probe_total(haystack, needle, probes, x, y, best_total)
            if total < best_total:
                best_total = total
                best_x = x
                best_y = y
                if best_total == 0:
                    return best_x, best_y, 0.0
            x += step
        y += step
    return best_x, best_y, best_total / len(probes)


def _refine(
    haystack: GrayBuffer,
    needle: GrayBuffer,
    probes: tuple[tuple[int, int], ...],
    x: int,
    y: int,
    step: int,
) -> tuple[int, int, float]:
    best_total = 255 * len(probes) + 1
    best_x, best_y = x, y
    y0 = max(0, y - step)
    y1 = min(haystack.height - needle.height, y + step)
    x0 = max(0, x - step)
    x1 = min(haystack.width - needle.width, x + step)
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            total = _probe_total(haystack, needle, probes, xx, yy, best_total)
            if total < best_total:
                best_total = total
                best_x, best_y = xx, yy
                if best_total == 0:
                    return best_x, best_y, 0.0
    return best_x, best_y, best_total / len(probes)


def _probe_total(
    haystack: GrayBuffer,
    needle: GrayBuffer,
    probes: tuple[tuple[int, int], ...],
    x: int,
    y: int,
    limit: int,
) -> int:
    hay = haystack.pixels
    pix = needle.pixels
    hay_width = haystack.width
    needle_width = needle.width
    total = 0
    for px, py in probes:
        total += abs(hay[(y + py) * hay_width + (x + px)] - pix[py * needle_width + px])
        if total >= limit:
            return limit
    return total
