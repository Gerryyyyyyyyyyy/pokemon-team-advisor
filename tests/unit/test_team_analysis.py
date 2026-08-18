"""Unit Tests für die defensive Typenanalyse eines Teams."""

from pokemon_team_advisor.team_analysis import (
    analyze_team_defense,
    summarize_team_weaknesses,
)

TEST_CHART: dict[str, dict[str, float]] = {
    "electric": {
        "fire": 1.0,
        "flying": 2.0,
        "grass": 0.5,
        "poison": 1.0,
        "water": 2.0,
    },
    "ground": {
        "fire": 2.0,
        "flying": 0.0,
        "grass": 0.5,
        "poison": 2.0,
        "water": 1.0,
    },
    "water": {
        "fire": 2.0,
        "flying": 1.0,
        "grass": 0.5,
        "poison": 1.0,
        "water": 0.5,
    },
}

TEST_TEAM: list[dict[str, object]] = [
    {
        "name": "bulbasaur",
        "type_1": "grass",
        "type_2": "poison",
    },
    {
        "name": "charizard",
        "type_1": "fire",
        "type_2": "flying",
    },
    {
        "name": "squirtle",
        "type_1": "water",
        "type_2": None,
    },
]


def test_analyze_team_defense_finds_shared_weakness() -> None:
    """Mehrere gefährdete Mitglieder für denselben Angriffstyp erkennen."""
    analysis = analyze_team_defense(TEST_TEAM, chart=TEST_CHART)

    assert analysis["electric"]["multipliers_by_member"] == {
        "bulbasaur": 0.5,
        "charizard": 2.0,
        "squirtle": 2.0,
    }
    assert analysis["electric"]["weak_members"] == (
        "charizard",
        "squirtle",
    )
    assert analysis["electric"]["resistant_members"] == ("bulbasaur",)
    assert analysis["electric"]["immune_members"] == ()
    assert analysis["electric"]["neutral_members"] == ()


def test_analyze_team_defense_distinguishes_immunity_and_neutrality() -> None:
    """Immunitäten getrennt von neutralen Treffern auswerten."""
    analysis = analyze_team_defense(TEST_TEAM, chart=TEST_CHART)

    assert analysis["ground"]["multipliers_by_member"] == {
        "bulbasaur": 1.0,
        "charizard": 0.0,
        "squirtle": 1.0,
    }
    assert analysis["ground"]["weak_members"] == ()
    assert analysis["ground"]["resistant_members"] == ()
    assert analysis["ground"]["immune_members"] == ("charizard",)
    assert analysis["ground"]["neutral_members"] == (
        "bulbasaur",
        "squirtle",
    )


def test_analyze_team_defense_handles_resistance_and_weakness() -> None:
    """Einzelne Schwäche und mehrere Resistenzen korrekt zuordnen."""
    analysis = analyze_team_defense(TEST_TEAM, chart=TEST_CHART)

    assert analysis["water"]["weak_members"] == ("charizard",)
    assert analysis["water"]["resistant_members"] == (
        "bulbasaur",
        "squirtle",
    )
    assert analysis["water"]["immune_members"] == ()
    assert analysis["water"]["neutral_members"] == ()


def test_summarize_team_weaknesses_ranks_shared_weaknesses_first() -> None:
    """Gemeinsame Schwächen vor einzelnen Schwächen anzeigen."""
    analysis = analyze_team_defense(TEST_TEAM, chart=TEST_CHART)

    summary = summarize_team_weaknesses(analysis)

    assert summary == [
        {
            "attacking_type": "electric",
            "weakness_count": 2,
            "resistance_count": 1,
            "immunity_count": 0,
            "neutral_count": 0,
            "maximum_multiplier": 2.0,
            "weak_members": ("charizard", "squirtle"),
        },
        {
            "attacking_type": "water",
            "weakness_count": 1,
            "resistance_count": 2,
            "immunity_count": 0,
            "neutral_count": 0,
            "maximum_multiplier": 2.0,
            "weak_members": ("charizard",),
        },
    ]
