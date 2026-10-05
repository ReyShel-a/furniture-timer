"""User-facing strings (en + ru) and the t() lookup."""

import ctypes
import os
import sys
from typing import Final

DEFAULT_LANG: Final[str] = "en"
SUPPORTED_LANGS: Final[tuple[str, ...]] = ("en", "ru")

_LOCALE_SISO639LANGNAME: Final[int] = 0x59
_LANG_RUSSIAN: Final[int] = 0x19

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
        "widget.field.project_number": "Project no.",
        "widget.field.project_name": "Project name",
        "widget.field.client": "Client",
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
        "settings.field.language": "Language",
        "settings.lang.en": "English",
        "settings.lang.ru": "Русский",
        "settings.btn.save": "Save",
        "settings.btn.cancel": "Cancel",
        "settings.btn.history": "History",
        "settings.error.rate": "Hourly rate must be a number >= 0",
        "settings.error.currency": "Currency must not be empty",
        "settings.error.idle_threshold": "Idle threshold must be an integer >= 1",
        "settings.error.language": "Language must be English or Russian",
        # Task 12 — history panel
        "history.dialog.title": "History",
        "history.col.start": "Start",
        "history.col.active": "Active",
        "history.col.cost": "Cost",
        "history.col.project_number": "No.",
        "history.col.project_name": "Name",
        "history.col.client": "Client",
        "history.empty": "No sessions yet",
        "history.btn.export": "Export CSV",
        "history.btn.clear": "Clear",
        "history.btn.close": "Close",
        "history.export.title": "Export sessions",
        "history.export.filter": "CSV files (*.csv)",
        "history.error.write": "Could not write CSV file",
        "history.error.clear": "Could not clear history",
        "history.error.summary": "Could not summarize project",
        "history.summary.pick": "Select a project",
        "history.summary.total": "{time}  ·  {cost:.2f}",
        "history.period.from": "From",
        "history.period.to": "To",
        # Task 13 — system tray
        "tray.action.show": "Show",
        "tray.action.quit": "Quit",
    },
    "ru": {
        "app.title": "Таймер работы",
        "btn.start": "Старт",
        "btn.pause": "Пауза",
        "btn.resume": "Продолжить",
        "btn.stop": "Стоп",
        "btn.settings": "Настройки",
        "btn.settings.glyph": "⚙",
        "btn.close": "Закрыть",
        "btn.close.glyph": "×",
        "widget.price_line": "{rate:.2f} {currency}/ч  ·  {cost:.2f} {currency}",
        "widget.tooltip.started": "Сессия начата в {time}",
        "widget.tooltip.not_started": "Нет активной сессии",
        "widget.field.project_number": "№ проекта",
        "widget.field.project_name": "Название проекта",
        "widget.field.client": "Имя клиента",
        "idle.dialog.title": "Обнаружен простой",
        "idle.dialog.message": "Простой {duration}",
        "idle.prompt.message": "Продолжить? Простой {duration}",
        "idle.btn.keep": "Оставить",
        "idle.btn.resume": "Продолжить",
        "idle.btn.discard": "Отбросить\nпростой",
        "idle.btn.keep.tooltip": "Остаться на паузе; простой записывается",
        "idle.btn.resume.tooltip": "Продолжить; простой записывается",
        "idle.btn.discard.tooltip": "Продолжить; простой не записывается",
        "settings.dialog.title": "Настройки",
        "settings.field.rate": "Ставка в час",
        "settings.field.currency": "Валюта",
        "settings.field.idle_threshold": "Порог простоя (с)",
        "settings.field.language": "Язык",
        "settings.lang.en": "English",
        "settings.lang.ru": "Русский",
        "settings.btn.save": "Сохранить",
        "settings.btn.cancel": "Отмена",
        "settings.btn.history": "История",
        "settings.error.rate": "Ставка должна быть числом >= 0",
        "settings.error.currency": "Валюта не должна быть пустой",
        "settings.error.idle_threshold": "Порог простоя — целое число >= 1",
        "settings.error.language": "Язык должен быть English или Русский",
        "history.dialog.title": "История",
        "history.col.start": "Начало",
        "history.col.active": "Активно",
        "history.col.cost": "Стоимость",
        "history.col.project_number": "№",
        "history.col.project_name": "Название",
        "history.col.client": "Клиент",
        "history.empty": "Сессий пока нет",
        "history.btn.export": "Экспорт CSV",
        "history.btn.clear": "Очистить",
        "history.btn.close": "Закрыть",
        "history.export.title": "Экспорт сессий",
        "history.export.filter": "Файлы CSV (*.csv)",
        "history.error.write": "Не удалось записать CSV-файл",
        "history.error.clear": "Не удалось очистить историю",
        "history.error.summary": "Не удалось посчитать итог",
        "history.summary.pick": "Выберите проект",
        "history.summary.total": "{time}  ·  {cost:.2f}",
        "history.period.from": "С",
        "history.period.to": "По",
        "tray.action.show": "Показать",
        "tray.action.quit": "Выход",
    },
}

_current_lang: str = DEFAULT_LANG


def language() -> str:
    """Language used by t() when the caller does not pass lang."""
    return _current_lang


def set_language(lang: str) -> None:
    """Switch the process language. Only en and ru are accepted."""
    global _current_lang
    if lang not in _STRINGS:
        raise ValueError(f"unsupported language: {lang!r}")
    _current_lang = lang


def language_from_tag(tag: str) -> str:
    """Map an OS locale tag to a supported language. ru* -> ru, otherwise en."""
    primary = tag.strip().replace("_", "-").split("-", 1)[0].lower()
    return "ru" if primary == "ru" else DEFAULT_LANG


def system_language() -> str:
    """UI language of the OS: Russian UI -> ru, anything else -> en."""
    return language_from_tag(_ui_language_tag())


def t(key: str, lang: str | None = None, **fmt: object) -> str:
    """Return localized string. Falls back to en, then to the key itself."""
    chosen = language() if lang is None else lang
    bundle = _STRINGS.get(chosen) or {}
    text = bundle.get(key) or _STRINGS[DEFAULT_LANG].get(key) or key
    return text.format(**fmt) if fmt else text


def _ui_language_tag() -> str:
    if sys.platform == "win32":
        return _windows_ui_tag()
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(name, "")
        if raw and raw.lower() not in {"c", "posix"}:
            return raw.split(".", 1)[0]
    return ""


def _windows_ui_tag() -> str:
    try:
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetUserDefaultUILanguage.restype = ctypes.c_uint16
        kernel32.GetLocaleInfoW.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        kernel32.GetLocaleInfoW.restype = ctypes.c_int
        lang_id = int(kernel32.GetUserDefaultUILanguage())
    except (AttributeError, OSError, ValueError):
        return ""
    if lang_id == 0:
        return ""
    buf = ctypes.create_unicode_buffer(16)
    if kernel32.GetLocaleInfoW(lang_id, _LOCALE_SISO639LANGNAME, buf, len(buf)) > 0:
        if buf.value:
            return buf.value
    if (lang_id & 0x3FF) == _LANG_RUSSIAN:
        return "ru"
    return ""
