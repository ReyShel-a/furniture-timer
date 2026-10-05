"""User-facing strings (en + ru) and the t() lookup."""

from typing import Final

DEFAULT_LANG: Final[str] = "en"

_STRINGS: Final[dict[str, dict[str, str]]] = {
    "en": {
        # Task 6 — widget
        "app.title": "Furniture Timer",
        "btn.start": "Start",
        "btn.pause": "Pause",
        "btn.resume": "Resume",
        "btn.stop": "Stop",
        "btn.settings": "Settings",
        "btn.settings.glyph": "⚙",
        "btn.close": "Close",
        "btn.close.glyph": "×",
        "widget.price_line": "{rate:.2f} {currency}/h  ·  {cost:.2f} {currency}",
        "widget.tooltip.started": "Session started at {time}",
        "widget.tooltip.not_started": "No active session",
    },
    "ru": {},  # filled in Task 14
}


def t(key: str, lang: str = DEFAULT_LANG, **fmt: object) -> str:
    """Return localized string. Falls back to en, then to the key itself."""
    bundle = _STRINGS.get(lang) or {}
    text = bundle.get(key) or _STRINGS[DEFAULT_LANG].get(key) or key
    return text.format(**fmt) if fmt else text
