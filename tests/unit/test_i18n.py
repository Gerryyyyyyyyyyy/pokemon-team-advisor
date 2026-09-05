"""Tests für die deutsche und englische Oberfläche."""

import pytest

from pokemon_team_advisor.i18n import (
    _TRANSLATIONS,
    _TYPE_NAMES,
    DEFAULT_LANGUAGE,
    LANGUAGE_OPTIONS,
    Language,
    language_from_option,
    text,
    type_name,
)


def test_languages_offer_complete_translation_sets() -> None:
    """Kein Sprachwechsel darf einzelne UI-Texte unübersetzt lassen."""
    assert set(_TRANSLATIONS[Language.GERMAN]) == set(_TRANSLATIONS[Language.ENGLISH])
    assert set(_TYPE_NAMES[Language.GERMAN]) == set(_TYPE_NAMES[Language.ENGLISH])
    assert len(_TYPE_NAMES[Language.GERMAN]) == 18


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("DE", Language.GERMAN),
        ("EN", Language.ENGLISH),
        ("FR", DEFAULT_LANGUAGE),
        (None, DEFAULT_LANGUAGE),
    ],
)
def test_language_from_option_uses_safe_default(
    option: object,
    expected: Language,
) -> None:
    """Nur die beiden sichtbaren Optionen als Sprachzustand übernehmen."""
    assert language_from_option(option) is expected


def test_language_options_match_supported_languages() -> None:
    """Der Umschalter bietet genau Deutsch und Englisch an."""
    assert LANGUAGE_OPTIONS == ("DE", "EN")


def test_text_formats_dynamic_values() -> None:
    """Dynamische Zahlen werden erst nach Auswahl der Sprache eingesetzt."""
    assert (
        text(
            Language.ENGLISH,
            "dataset_summary",
            pokemon_count=1025,
            type_count=18,
        )
        == "1025 Pokémon · 18 types · local, read-only data"
    )


def test_type_name_rejects_unknown_type() -> None:
    """Unkontrollierte Typwerte nicht ungeprüft in der UI darstellen."""
    with pytest.raises(ValueError, match="Unknown Pokémon type"):
        type_name(Language.ENGLISH, "cosmic")


def test_text_rejects_unknown_key() -> None:
    """Tippfehler in UI-Schlüsseln während Entwicklung und Tests sichtbar machen."""
    with pytest.raises(ValueError, match="Unknown translation key"):
        text(Language.GERMAN, "missing-key")
