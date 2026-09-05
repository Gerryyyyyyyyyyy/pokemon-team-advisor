"""Tests für das erklärbare Ranking des sechsten Teammitglieds."""

from copy import deepcopy

import pytest

from pokemon_team_advisor.recommender import (
    Recommendation,
    RecommendationWeights,
    recommend_team_members,
)
from pokemon_team_advisor.roles import Role
from pokemon_team_advisor.type_effectiveness import TypeChart


def _pokemon(
    pokemon_id: int,
    name: str,
    *,
    type_1: str = "normal",
    type_2: str | None = None,
    hp: int = 70,
    attack: int = 70,
    defense: int = 70,
    special_attack: int = 70,
    special_defense: int = 70,
    speed: int = 70,
    is_final_evolution: bool = True,
) -> dict[str, object]:
    """Kleinen vollständigen Pokémon-Datensatz für Rankingtests erzeugen."""
    stats = {
        "hp": hp,
        "attack": attack,
        "defense": defense,
        "special_attack": special_attack,
        "special_defense": special_defense,
        "speed": speed,
    }
    return {
        "id": pokemon_id,
        "name": name,
        "type_1": type_1,
        "type_2": type_2,
        **stats,
        "base_stat_total": sum(stats.values()),
        "is_final_evolution": is_final_evolution,
    }


@pytest.fixture
def type_chart() -> TypeChart:
    """Kleine vollständige Matrix für alle in den Tests verwendeten Typen."""
    supported_types = {
        "bug",
        "electric",
        "fire",
        "grass",
        "ground",
        "normal",
        "psychic",
        "water",
    }
    chart: dict[str, dict[str, float]] = {
        attacking_type: {defending_type: 1.0 for defending_type in supported_types}
        for attacking_type in supported_types
    }
    chart["fire"].update(
        {
            "bug": 2.0,
            "fire": 0.5,
            "grass": 2.0,
            "water": 0.5,
        }
    )
    chart["water"].update(
        {
            "fire": 2.0,
            "grass": 0.5,
            "ground": 2.0,
            "water": 0.5,
        }
    )
    chart["electric"].update(
        {
            "electric": 0.5,
            "grass": 0.5,
            "ground": 0.0,
            "water": 2.0,
        }
    )
    return chart


@pytest.fixture
def balanced_team() -> list[dict[str, object]]:
    """Fünf neutrale Teammitglieder mit unterschiedlichen Stärken."""
    return [_pokemon(index, f"team-{index}", hp=60 + index) for index in range(1, 6)]


def _team_ids(team: list[dict[str, object]]) -> list[int]:
    """Validierte Test-IDs aus den kleinen Teamdatensätzen lesen."""
    team_ids: list[int] = []
    for member in team:
        pokemon_id = member["id"]
        if isinstance(pokemon_id, bool) or not isinstance(pokemon_id, int):
            raise AssertionError("Test fixture id must be an integer.")
        team_ids.append(pokemon_id)
    return team_ids


def _by_name(
    recommendations: list[Recommendation],
) -> dict[str, Recommendation]:
    """Empfehlungen für gezielte Assertions nach Namen indizieren."""
    return {recommendation["name"]: recommendation for recommendation in recommendations}


def test_recommendations_exclude_team_and_default_to_final_evolutions(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    final_candidate = _pokemon(100, "final-candidate")
    weedle = _pokemon(
        13,
        "weedle",
        type_1="bug",
        hp=40,
        attack=35,
        defense=30,
        special_attack=20,
        special_defense=20,
        speed=50,
        is_final_evolution=False,
    )
    pokemon = [*balanced_team, final_candidate, weedle]

    recommendations = recommend_team_members(
        _team_ids(balanced_team),
        pokemon,
        chart=type_chart,
    )

    assert [item["name"] for item in recommendations] == ["final-candidate"]
    assert not ({item["pokemon_id"] for item in recommendations} & set(_team_ids(balanced_team)))


def test_non_final_evolutions_can_be_included_explicitly(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    pokemon = [
        *balanced_team,
        _pokemon(13, "weedle", type_1="bug", is_final_evolution=False),
    ]

    recommendations = recommend_team_members(
        _team_ids(balanced_team),
        pokemon,
        chart=type_chart,
        include_non_final=True,
    )

    assert [item["name"] for item in recommendations] == ["weedle"]


def test_resistance_to_shared_weakness_improves_defensive_ranking(
    type_chart: TypeChart,
) -> None:
    team = [_pokemon(index, f"grass-{index}", type_1="grass") for index in range(1, 6)]
    water_guard = _pokemon(100, "water-guard", type_1="water")
    bug_risk = _pokemon(101, "bug-risk", type_1="bug")

    recommendations = recommend_team_members(
        _team_ids(team),
        [*team, water_guard, bug_risk],
        chart=type_chart,
        limit=2,
    )
    by_name = _by_name(recommendations)

    assert recommendations[0]["name"] == "water-guard"
    assert by_name["water-guard"]["defensive_score"] > by_name["bug-risk"]["defensive_score"]
    assert "fire" in by_name["water-guard"]["covered_threats"]


def test_missing_special_role_outranks_redundant_physical_role(
    type_chart: TypeChart,
) -> None:
    team = [
        _pokemon(
            index,
            f"physical-{index}",
            attack=140,
            special_attack=40,
            speed=90,
        )
        for index in range(1, 6)
    ]
    special_candidate = _pokemon(
        100,
        "special-candidate",
        attack=40,
        special_attack=140,
        speed=90,
    )
    physical_candidate = _pokemon(
        101,
        "physical-candidate",
        attack=140,
        special_attack=40,
        speed=90,
    )

    recommendations = recommend_team_members(
        _team_ids(team),
        [*team, special_candidate, physical_candidate],
        chart=type_chart,
        limit=2,
    )
    by_name = _by_name(recommendations)

    assert recommendations[0]["name"] == "special-candidate"
    assert by_name["special-candidate"]["role_score"] > by_name["physical-candidate"]["role_score"]
    assert Role.SPECIAL_ATTACKER in by_name["special-candidate"]["matched_roles"]


def test_absolute_strength_breaks_equal_profile_tie(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    weak_candidate = _pokemon(
        100,
        "weak-balanced",
        hp=40,
        attack=40,
        defense=40,
        special_attack=40,
        special_defense=40,
        speed=40,
    )
    strong_candidate = _pokemon(
        101,
        "strong-balanced",
        hp=100,
        attack=100,
        defense=100,
        special_attack=100,
        special_defense=100,
        speed=100,
    )

    recommendations = recommend_team_members(
        _team_ids(balanced_team),
        [*balanced_team, weak_candidate, strong_candidate],
        chart=type_chart,
        limit=2,
    )
    by_name = _by_name(recommendations)

    assert recommendations[0]["name"] == "strong-balanced"
    assert by_name["strong-balanced"]["strength_score"] > by_name["weak-balanced"]["strength_score"]


def test_score_components_are_bounded_and_reconstruct_total(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    weights = RecommendationWeights(
        defensive=0.5,
        role=0.3,
        strength=0.2,
    )
    candidate = _pokemon(100, "candidate", type_1="psychic")

    recommendation = recommend_team_members(
        _team_ids(balanced_team),
        [*balanced_team, candidate],
        chart=type_chart,
        weights=weights,
    )[0]

    assert 0.0 <= recommendation["defensive_score"] <= 1.0
    assert 0.0 <= recommendation["role_score"] <= 1.0
    assert 0.0 <= recommendation["strength_score"] <= 1.0
    expected_total = 100.0 * (
        weights.defensive * recommendation["defensive_score"]
        + weights.role * recommendation["role_score"]
        + weights.strength * recommendation["strength_score"]
    )
    assert recommendation["total_score"] == pytest.approx(expected_total)


def test_recommendation_contains_structured_explanations(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    recommendation = recommend_team_members(
        _team_ids(balanced_team),
        [*balanced_team, _pokemon(100, "candidate")],
        chart=type_chart,
    )[0]

    assert isinstance(recommendation["matched_roles"], tuple)
    assert recommendation["matched_roles"]
    assert all(isinstance(role, Role) for role in recommendation["matched_roles"])
    assert isinstance(recommendation["covered_threats"], tuple)


def test_limit_returns_at_most_five_candidates_and_sorting_is_deterministic(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    candidates = [
        _pokemon(100 + index, name)
        for index, name in enumerate(["zeta", "eta", "delta", "gamma", "beta", "alpha", "epsilon"])
    ]

    recommendations = recommend_team_members(
        _team_ids(balanced_team),
        [*balanced_team, *candidates],
        chart=type_chart,
    )

    assert len(recommendations) == 5
    assert [item["name"] for item in recommendations] == [
        "alpha",
        "beta",
        "delta",
        "epsilon",
        "eta",
    ]


@pytest.mark.parametrize(
    "team_ids",
    [
        [1, 2, 3, 4],
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 4],
    ],
)
def test_team_must_contain_exactly_five_unique_members(
    team_ids: list[int],
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    with pytest.raises(ValueError, match="five unique"):
        recommend_team_members(
            team_ids,
            balanced_team,
            chart=type_chart,
        )


def test_unknown_team_member_is_rejected(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    with pytest.raises(ValueError, match="Unknown team member id: 999"):
        recommend_team_members(
            [1, 2, 3, 4, 999],
            balanced_team,
            chart=type_chart,
        )


def test_valid_weights_are_immutable() -> None:
    weights = RecommendationWeights(defensive=0.5, role=0.3, strength=0.2)

    with pytest.raises((AttributeError, TypeError)):
        weights.defensive = 0.9  # type: ignore[misc]


@pytest.mark.parametrize(
    ("defensive", "role", "strength"),
    [
        (0.5, 0.5, 0.5),
        (-0.1, 0.6, 0.5),
        (float("nan"), 0.5, 0.5),
    ],
)
def test_invalid_weights_are_rejected(
    defensive: float,
    role: float,
    strength: float,
) -> None:
    with pytest.raises(ValueError):
        RecommendationWeights(
            defensive=defensive,
            role=role,
            strength=strength,
        )


def test_ranking_does_not_mutate_inputs(
    balanced_team: list[dict[str, object]],
    type_chart: TypeChart,
) -> None:
    pokemon = [*balanced_team, _pokemon(100, "candidate")]
    original_pokemon = deepcopy(pokemon)
    original_chart = deepcopy(type_chart)

    recommend_team_members(
        _team_ids(balanced_team),
        pokemon,
        chart=type_chart,
    )

    assert pokemon == original_pokemon
    assert type_chart == original_chart
