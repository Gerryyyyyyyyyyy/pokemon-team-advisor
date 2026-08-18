"""Sicherheitsnahe Unit Tests für die Streamlit-Datenübergabe."""

import pandas as pd  # type: ignore[import-untyped]
import pytest

from pokemon_team_advisor.app import (
    filter_pokemon,
    safe_sprite_url,
    selected_team_records,
)


def _pokemon_data() -> pd.DataFrame:
    """Sechs kleine gültige UI-Datensätze erzeugen."""
    rows = []
    for pokemon_id in range(1, 7):
        rows.append(
            {
                "id": pokemon_id,
                "name": f"pokemon-{pokemon_id}",
                "species_name": f"pokemon-{pokemon_id}",
                "type_1": "normal",
                "type_2": None,
                "base_stat_total": 300,
                "sprite_url": (
                    "https://raw.githubusercontent.com/PokeAPI/sprites/"
                    f"master/sprites/pokemon/{pokemon_id}.png"
                ),
                "generation": 1,
                "evolution_stage": 0,
                "evolution_max_stage": 0,
                "is_final_evolution": True,
            }
        )
    return pd.DataFrame(rows)


def _filter_data() -> pd.DataFrame:
    """Unterschiedliche Pokémon für Such-, Filter- und Sortiertests erzeugen."""
    return pd.DataFrame(
        [
            {
                "id": 1,
                "name": "bulbasaur",
                "type_1": "grass",
                "type_2": "poison",
                "base_stat_total": 318,
                "generation": 1,
                "evolution_stage": 0,
                "is_final_evolution": False,
            },
            {
                "id": 25,
                "name": "pikachu",
                "type_1": "electric",
                "type_2": None,
                "base_stat_total": 320,
                "generation": 1,
                "evolution_stage": 1,
                "is_final_evolution": False,
            },
            {
                "id": 122,
                "name": "mr-mime",
                "type_1": "psychic",
                "type_2": "fairy",
                "base_stat_total": 460,
                "generation": 1,
                "evolution_stage": 1,
                "is_final_evolution": True,
            },
            {
                "id": 248,
                "name": "tyranitar",
                "type_1": "rock",
                "type_2": "dark",
                "base_stat_total": 600,
                "generation": 2,
                "evolution_stage": 2,
                "is_final_evolution": True,
            },
        ]
    )


@pytest.mark.parametrize(
    ("value", "is_allowed"),
    [
        (
            "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
            True,
        ),
        ("http://raw.githubusercontent.com/PokeAPI/sprites/test.png", False),
        ("https://malicious.example/track.png", False),
        ("https://raw.githubusercontent.com/other/project/image.png", False),
        ("data:image/png;base64,unsafe", False),
        (None, False),
    ],
)
def test_safe_sprite_url_uses_strict_allowlist(
    value: object,
    is_allowed: bool,
) -> None:
    """Nur den festgelegten HTTPS-Host und Repositorypfad zulassen."""
    result = safe_sprite_url(value)

    assert (result is not None) is is_allowed


def test_selected_team_records_rejects_unknown_input() -> None:
    """Freie oder SQL-artige Eingaben nicht als Datensatzoption akzeptieren."""
    with pytest.raises(ValueError, match="unknown Pokémon"):
        selected_team_records(
            _pokemon_data(),
            ["pokemon-1'; DROP TABLE pokemon; --"],
        )


@pytest.mark.parametrize(
    "selected_names",
    [
        ["pokemon-1", "pokemon-1"],
        [f"pokemon-{pokemon_id}" for pokemon_id in range(1, 7)],
    ],
)
def test_selected_team_records_enforces_selection_limit(
    selected_names: list[str],
) -> None:
    """Nur höchstens fünf eindeutige Optionen an die Fachlogik übergeben."""
    with pytest.raises(ValueError, match="at most five unique"):
        selected_team_records(_pokemon_data(), selected_names)


def test_selected_team_records_removes_untrusted_sprite_url() -> None:
    """Eine manipulierte Bildquelle nicht an Streamlit weiterreichen."""
    pokemon = _pokemon_data()
    pokemon.loc[pokemon["name"].eq("pokemon-1"), "sprite_url"] = (
        "https://malicious.example/track.png"
    )

    records = selected_team_records(pokemon, ["pokemon-1"])

    assert records[0]["sprite_url"] is None


@pytest.mark.parametrize(
    ("search_text", "expected_name"),
    [
        ("Mr Mime", "mr-mime"),
        ("#025", "pikachu"),
        ("BULBA", "bulbasaur"),
    ],
)
def test_filter_pokemon_searches_names_and_pokedex_ids(
    search_text: str,
    expected_name: str,
) -> None:
    """Suche soll Großschreibung, Bindestriche und Pokédex-IDs unterstützen."""
    result = filter_pokemon(_filter_data(), search_text=search_text)

    assert result["name"].tolist() == [expected_name]


def test_filter_pokemon_combines_filters() -> None:
    """Alle aktiven Filter werden gemeinsam statt unabhängig angewendet."""
    result = filter_pokemon(
        _filter_data(),
        selected_types=["dark"],
        selected_generations=[2],
        evolution_stage=2,
        final_only=True,
        dual_type_only=True,
        minimum_base_stat_total=500,
    )

    assert result["name"].tolist() == ["tyranitar"]


def test_filter_pokemon_sorts_strongest_first() -> None:
    """Die gewählte Sortierung soll ein stabiles Ergebnis liefern."""
    result = filter_pokemon(_filter_data(), sort_by="Stärkste zuerst")

    assert result["name"].tolist() == [
        "tyranitar",
        "mr-mime",
        "pikachu",
        "bulbasaur",
    ]


def test_filter_pokemon_treats_search_as_literal_text() -> None:
    """Regex-Sonderzeichen dürfen die Suche weder ändern noch zum Absturz bringen."""
    result = filter_pokemon(_filter_data(), search_text="[.*")

    assert result.empty


def test_filter_pokemon_rejects_unknown_filter_values() -> None:
    """Auch programmatisch manipulierte Typfilter werden zurückgewiesen."""
    with pytest.raises(ValueError, match="unknown Pokémon type"):
        filter_pokemon(_filter_data(), selected_types=["cosmic"])
