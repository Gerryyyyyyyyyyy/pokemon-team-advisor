"""Unit Tests für die Python-Grenzen der Live-Suchkomponente."""

from types import SimpleNamespace

import pytest
import streamlit as st

import pokemon_team_advisor.live_search as live_search_module
from pokemon_team_advisor.live_search import _limited_text, live_search_input


def test_limited_text_keeps_strings_within_limit() -> None:
    """Die Python-Seite erzwingt die Länge zusätzlich zum Browserfeld."""
    assert _limited_text("pikachu", max_chars=4) == "pika"


@pytest.mark.parametrize("value", [None, 25, ["pikachu"]])
def test_limited_text_rejects_non_strings(value: object) -> None:
    """Manipulierte Komponentenwerte werden nicht als Suchtext übernommen."""
    assert _limited_text(value, max_chars=80) == ""


def test_live_search_rejects_invalid_configuration() -> None:
    """Fehlerhafte Entwicklerparameter früh und verständlich ablehnen."""
    with pytest.raises(ValueError, match="max_chars must be positive"):
        live_search_input(
            "Suche",
            placeholder="Pokémon",
            key="test-search",
            max_chars=0,
        )


def test_live_search_prefers_current_change_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein neuer Tastendruck muss einen älteren Session-Wert sofort ersetzen."""
    monkeypatch.setitem(
        st.session_state,
        "live-search-test",
        {"value": "alter wert"},
    )

    def component_result(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(value="alter wert", changed="ivysaur")

    monkeypatch.setattr(
        live_search_module,
        "_live_search_component",
        component_result,
    )

    result = live_search_input(
        "Suche",
        placeholder="Pokémon",
        key="live-search-test",
    )

    assert result == "ivysaur"
