import pytest

from furniture_timer.i18n import _STRINGS, language_from_tag, set_language, system_language, t


def test_russian_catalog_matches_english() -> None:
    assert set(_STRINGS["ru"]) == set(_STRINGS["en"])


@pytest.mark.parametrize("key", sorted(_STRINGS["en"]))
def test_russian_strings_resolve(key: str) -> None:
    assert t(
        key,
        lang="ru",
        rate=0.0,
        cost=0.0,
        currency="₽",
        time="00:00",
        duration="00:05:00",
    ) != key


def test_language_from_tag() -> None:
    assert language_from_tag("ru-RU") == "ru"
    assert language_from_tag("ru_RU") == "ru"
    assert language_from_tag("en-US") == "en"
    assert language_from_tag("") == "en"


def test_system_language_uses_ui_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("furniture_timer.i18n._ui_language_tag", lambda: "ru-RU")
    assert system_language() == "ru"
    monkeypatch.setattr("furniture_timer.i18n._ui_language_tag", lambda: "en-US")
    assert system_language() == "en"


def test_set_language_changes_default_lookup() -> None:
    set_language("ru")
    assert t("btn.start") == "Старт"
    set_language("en")
    assert t("btn.start") == "Start"


def test_set_language_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        set_language("de")
