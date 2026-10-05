"""Pure display formatting helpers (no Qt)."""

from datetime import datetime


def format_hms(seconds: float) -> str:
    """Whole elapsed seconds as HH:MM:SS; hours widen past 99, negatives clamp to zero."""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_clock(ts: int) -> str:
    """Unix timestamp as local wall-clock HH:MM."""
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def format_datetime(ts: int) -> str:
    """Unix timestamp as local YYYY-MM-DD HH:MM."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
