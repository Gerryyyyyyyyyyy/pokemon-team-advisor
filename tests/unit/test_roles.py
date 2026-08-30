"""Tests für das transparente Multi-Label-Rollenmodell."""

from copy import deepcopy

import pytest

from pokemon_team_advisor.roles import Role, RoleScore, analyze_pokemon_roles


@pytest.fixture
def pokemon() -> list[dict[str, object]]:
    """Kleine Referenzmenge mit klaren und absichtlich ähnlichen Profilen."""
    return [
        {
            "id": 1,
            "name": "weak-balanced",
            "hp": 40,
            "attack": 40,
            "defense": 40,
            "special_attack": 40,
            "special_defense": 40,
            "speed": 40,
            "base_stat_total": 240,
        },
        {
            "id": 2,
            "name": "strong-balanced",
            "hp": 100,
            "attack": 100,
            "defense": 100,
            "special_attack": 100,
            "special_defense": 100,
            "speed": 100,
            "base_stat_total": 600,
        },
        {
            "id": 3,
            "name": "physical-attacker",
            "hp": 60,
            "attack": 140,
            "defense": 50,
            "special_attack": 40,
            "special_defense": 50,
            "speed": 130,
            "base_stat_total": 470,
        },
        {
            "id": 4,
            "name": "special-attacker",
            "hp": 60,
            "attack": 40,
            "defense": 50,
            "special_attack": 140,
            "special_defense": 50,
            "speed": 130,
            "base_stat_total": 470,
        },
        {
            "id": 5,
            "name": "physical-defender",
            "hp": 100,
            "attack": 40,
            "defense": 130,
            "special_attack": 40,
            "special_defense": 50,
            "speed": 20,
            "base_stat_total": 380,
        },
        {
            "id": 6,
            "name": "special-defender",
            "hp": 100,
            "attack": 40,
            "defense": 50,
            "special_attack": 40,
            "special_defense": 130,
            "speed": 20,
            "base_stat_total": 380,
        },
    ]


@pytest.fixture
def known_pokemon() -> list[dict[str, object]]:
    """Reale Grenzfälle aus dem vollständigen PokéAPI-Snapshot."""
    return [
        {
            "id": 25,
            "name": "pikachu",
            "hp": 35,
            "attack": 55,
            "defense": 40,
            "special_attack": 50,
            "special_defense": 50,
            "speed": 90,
            "base_stat_total": 320,
        },
        {
            "id": 213,
            "name": "shuckle",
            "hp": 20,
            "attack": 10,
            "defense": 230,
            "special_attack": 10,
            "special_defense": 230,
            "speed": 5,
            "base_stat_total": 505,
        },
        {
            "id": 242,
            "name": "blissey",
            "hp": 255,
            "attack": 10,
            "defense": 10,
            "special_attack": 75,
            "special_defense": 135,
            "speed": 55,
            "base_stat_total": 540,
        },
        {
            "id": 292,
            "name": "shedinja",
            "hp": 1,
            "attack": 90,
            "defense": 45,
            "special_attack": 30,
            "special_defense": 30,
            "speed": 40,
            "base_stat_total": 236,
        },
        {
            "id": 445,
            "name": "garchomp",
            "hp": 108,
            "attack": 130,
            "defense": 95,
            "special_attack": 80,
            "special_defense": 85,
            "speed": 102,
            "base_stat_total": 600,
        },
    ]


def _scores_by_role(
    analysis: dict[int, tuple[RoleScore, ...]],
    pokemon_id: int,
) -> dict[Role, RoleScore]:
    """Die sechs Rollenscores eines Pokémon nach Rolle indizieren."""
    return {
        score["role"]: score for score in analysis[pokemon_id] if isinstance(score["role"], Role)
    }


def _assigned_roles(
    analysis: dict[int, tuple[RoleScore, ...]],
    pokemon_id: int,
) -> set[Role]:
    """Nur die tatsächlich vergebenen Rollen eines Pokémon zurückgeben."""
    return {
        score["role"]
        for score in analysis[pokemon_id]
        if score["assigned"] is True and isinstance(score["role"], Role)
    }


def test_analyze_pokemon_roles_returns_every_role_for_every_pokemon(
    pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles(pokemon)

    assert set(analysis) == {1, 2, 3, 4, 5, 6}
    assert all(len(scores) == len(Role) for scores in analysis.values())
    assert all({score["role"] for score in scores} == set(Role) for scores in analysis.values())


def test_role_scores_are_bounded_and_assign_one_to_three_roles(
    pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles(pokemon)

    for scores in analysis.values():
        assert all(0.0 <= float(score["fit_score"]) <= 1.0 for score in scores)
        assert all(0.0 <= float(score["strength_score"]) <= 1.0 for score in scores)
        assigned_count = sum(score["assigned"] is True for score in scores)
        assert 1 <= assigned_count <= 3


def test_fast_physical_pokemon_receives_multiple_matching_roles(
    pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles(pokemon)

    assert {
        Role.PHYSICAL_ATTACKER,
        Role.FAST_ATTACKER,
    } <= _assigned_roles(analysis, 3)


def test_fast_special_pokemon_receives_multiple_matching_roles(
    pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles(pokemon)

    assert {
        Role.SPECIAL_ATTACKER,
        Role.FAST_ATTACKER,
    } <= _assigned_roles(analysis, 4)


def test_defensive_specializations_are_distinguished(
    pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles(pokemon)

    assert Role.PHYSICAL_DEFENDER in _assigned_roles(analysis, 5)
    assert Role.SPECIAL_DEFENDER in _assigned_roles(analysis, 6)


def test_all_rounder_fit_is_separate_from_absolute_strength(
    pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles(pokemon)
    weak = _scores_by_role(analysis, 1)[Role.ALL_ROUNDER]
    strong = _scores_by_role(analysis, 2)[Role.ALL_ROUNDER]

    assert float(weak["fit_score"]) == pytest.approx(float(strong["fit_score"]))
    assert float(weak["strength_score"]) < float(strong["strength_score"])
    assert Role.ALL_ROUNDER in _assigned_roles(analysis, 1)
    assert Role.ALL_ROUNDER in _assigned_roles(analysis, 2)


def test_blissey_is_not_misclassified_as_physical_defender(
    pokemon: list[dict[str, object]],
    known_pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles([*pokemon, *known_pokemon])

    assert Role.SPECIAL_DEFENDER in _assigned_roles(analysis, 242)
    assert Role.PHYSICAL_DEFENDER not in _assigned_roles(analysis, 242)


def test_shedinja_is_not_misclassified_as_fast_attacker(
    pokemon: list[dict[str, object]],
    known_pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles([*pokemon, *known_pokemon])

    assert Role.PHYSICAL_ATTACKER in _assigned_roles(analysis, 292)
    assert Role.FAST_ATTACKER not in _assigned_roles(analysis, 292)


def test_garchomp_receives_physical_attacker_role(
    pokemon: list[dict[str, object]],
    known_pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles([*pokemon, *known_pokemon])

    assert Role.PHYSICAL_ATTACKER in _assigned_roles(analysis, 445)


def test_pikachu_remains_a_fast_attacker(
    pokemon: list[dict[str, object]],
    known_pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles([*pokemon, *known_pokemon])

    assert Role.FAST_ATTACKER in _assigned_roles(analysis, 25)


def test_shuckle_keeps_both_defensive_roles(
    pokemon: list[dict[str, object]],
    known_pokemon: list[dict[str, object]],
) -> None:
    analysis = analyze_pokemon_roles([*pokemon, *known_pokemon])

    assert {
        Role.PHYSICAL_DEFENDER,
        Role.SPECIAL_DEFENDER,
    } <= _assigned_roles(analysis, 213)


def test_analysis_does_not_mutate_input(
    pokemon: list[dict[str, object]],
) -> None:
    original = deepcopy(pokemon)

    analyze_pokemon_roles(pokemon)

    assert pokemon == original


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("hp", 0),
        ("attack", -1),
        ("speed", "fast"),
    ],
)
def test_invalid_stats_are_rejected(
    pokemon: list[dict[str, object]],
    field: str,
    invalid_value: object,
) -> None:
    pokemon[0][field] = invalid_value

    with pytest.raises(ValueError, match=field):
        analyze_pokemon_roles(pokemon)


def test_incorrect_base_stat_total_is_rejected(
    pokemon: list[dict[str, object]],
) -> None:
    pokemon[0]["base_stat_total"] = 999

    with pytest.raises(ValueError, match="base_stat_total"):
        analyze_pokemon_roles(pokemon)


def test_duplicate_ids_are_rejected(
    pokemon: list[dict[str, object]],
) -> None:
    pokemon[1]["id"] = pokemon[0]["id"]

    with pytest.raises(ValueError, match="Duplicate Pokemon id"):
        analyze_pokemon_roles(pokemon)


def test_empty_reference_data_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one Pokemon"):
        analyze_pokemon_roles([])


@pytest.mark.parametrize(
    ("minimum_fit_score", "maximum_roles"),
    [
        (-0.1, 3),
        (1.1, 3),
        (0.8, 0),
        (0.8, 7),
    ],
)
def test_invalid_assignment_configuration_is_rejected(
    pokemon: list[dict[str, object]],
    minimum_fit_score: float,
    maximum_roles: int,
) -> None:
    with pytest.raises(ValueError):
        analyze_pokemon_roles(
            pokemon,
            minimum_fit_score=minimum_fit_score,
            maximum_roles=maximum_roles,
        )
