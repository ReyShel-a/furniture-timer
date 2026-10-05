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
        # Task 8 — idle modal
        "idle.dialog.title": "Idle detected",
        "idle.dialog.message": "Idle {duration}",
        "idle.prompt.message": "Resume? Idle {duration}",
        "idle.btn.keep": "Keep",
        "idle.btn.resume": "Resume",
        "idle.btn.discard": "Discard idle",
        "idle.btn.keep.tooltip": "Stay paused; idle time is recorded",
        "idle.btn.resume.tooltip": "Continue; idle time is recorded",
        "idle.btn.discard.tooltip": "Continue; idle time is not recorded",
        # Task 11 — settings dialog
        "settings.dialog.title": "Settings",
        "settings.field.rate": "Hourly rate",
        "settings.field.currency": "Currency",
        "settings.field.idle_threshold": "Idle threshold (s)",
        "settings.btn.save": "Save",
        "settings.btn.cancel": "Cancel",
        "settings.btn.history": "History",
        "settings.error.rate": "Hourly rate must be a number >= 0",
        "settings.error.currency": "Currency must not be empty",
        "settings.error.idle_threshold": "Idle threshold must be an integer >= 1",
        # Task 12 — history panel
        "history.dialog.title": "History",
        "history.col.start": "Start",
        "history.col.active": "Active",
        "history.col.cost": "Cost",
        "history.empty": "No sessions yet",
        "history.btn.export": "Export CSV",
        "history.btn.close": "Close",
        "history.export.title": "Export sessions",
        "history.export.filter": "CSV files (*.csv)",
        "history.error.write": "Could not write CSV file",
        # Task 13 — system tray
        "tray.action.show": "Show",
        "tray.action.quit": "Quit",
    },
    "ru": {},  # filled in Task 14
}


def t(key: str, lang: str = DEFAULT_LANG, **fmt: object) -> str:
    """Return localized string. Falls back to en, then to the key itself."""
    bundle = _STRINGS.get(lang) or {}
    text = bundle.get(key) or _STRINGS[DEFAULT_LANG].get(key) or key
    return text.format(**fmt) if fmt else text
