"""Defensive Typenabdeckung eines Pokémon-Teams analysieren."""

from collections.abc import Iterable, Mapping
from typing import TypedDict

from pokemon_team_advisor.type_effectiveness import (
    TypeChart,
    calculate_type_multiplier,
)


class TeamDefenseEntry(TypedDict):
    """Defensive Teamauswertung für einen angreifenden Typ."""

    multipliers_by_member: dict[str, float]
    weak_members: tuple[str, ...]
    resistant_members: tuple[str, ...]
    immune_members: tuple[str, ...]
    neutral_members: tuple[str, ...]


class TeamWeaknessSummary(TypedDict):
    """Kompakte Zusammenfassung eines gefährlichen Angriffstyps."""

    attacking_type: str
    weakness_count: int
    resistance_count: int
    immunity_count: int
    neutral_count: int
    maximum_multiplier: float
    weak_members: tuple[str, ...]


def _require_non_empty_string(value: object, *, field: str) -> str:
    """Einen nicht leeren String aus einem Teamdatensatz validieren."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty string.")

    return value


def _extract_member_types(member: Mapping[str, object]) -> tuple[str, ...]:
    """Den primären und optionalen sekundären Typ eines Mitglieds lesen."""
    type_1 = _require_non_empty_string(
        member.get("type_1"),
        field="type_1",
    )
    raw_type_2 = member.get("type_2")

    if raw_type_2 is None:
        return (type_1,)

    type_2 = _require_non_empty_string(raw_type_2, field="type_2")

    if type_1 == type_2:
        raise ValueError("A team member must not have duplicate types.")

    return type_1, type_2


def analyze_team_defense(
    team: Iterable[Mapping[str, object]],
    *,
    chart: TypeChart,
) -> dict[str, TeamDefenseEntry]:
    """Defensive Reaktionen eines Teams auf alle Angriffstypen berechnen.

    Für jeden Angriffstyp wird der Multiplikator jedes Teammitglieds bestimmt.
    Anschließend werden die Mitglieder in vier verständliche Gruppen eingeordnet:

    - Schwäche: Multiplikator größer als 1
    - Resistenz: Multiplikator zwischen 0 und 1
    - Immunität: Multiplikator genau 0
    - Neutralität: Multiplikator genau 1

    Args:
        team: Ein bis sechs Pokémon-Datensätze mit ``name``, ``type_1`` und
            optionalem ``type_2``.
        chart: Typenmatrix mit angreifenden Typen als äußeren Schlüsseln.

    Returns:
        Eine nach Angriffstyp geordnete defensive Teamauswertung.

    Raises:
        ValueError: Wenn das Team leer oder zu groß ist, Namen doppelt vorkommen
            oder benötigte Felder ungültig sind.
    """
    members = list(team)

    if not members:
        raise ValueError("Team must contain at least one member.")

    # Die Spielregeln erlauben höchstens sechs Pokémon. Die spätere
    # Empfehlungsfunktion verwendet normalerweise ein Team aus höchstens fünf.
    if len(members) > 6:
        raise ValueError("Team must contain at most six members.")

    prepared_members: list[tuple[str, tuple[str, ...]]] = []
    seen_names: set[str] = set()

    # Das gesamte Team wird validiert, bevor die erste Berechnung beginnt.
    # Dadurch erhalten wir bei ungültigen Eingaben kein halbfertiges Ergebnis.
    for index, member in enumerate(members):
        name = _require_non_empty_string(
            member.get("name"),
            field=f"team[{index}].name",
        )

        if name in seen_names:
            raise ValueError(f"Duplicate team member: {name}.")

        seen_names.add(name)
        defending_types = _extract_member_types(member)
        prepared_members.append((name, defending_types))

    if not chart:
        raise ValueError("Type chart must not be empty.")

    analysis: dict[str, TeamDefenseEntry] = {}

    # Sortieren hält Tabellen und spätere Streamlit-Ausgaben reproduzierbar.
    for attacking_type in sorted(chart):
        multipliers_by_member: dict[str, float] = {}
        weak_members: list[str] = []
        resistant_members: list[str] = []
        immune_members: list[str] = []
        neutral_members: list[str] = []

        for member_name, defending_types in prepared_members:
            multiplier = calculate_type_multiplier(
                attacking_type,
                defending_types,
                chart=chart,
            )
            multipliers_by_member[member_name] = multiplier

            if multiplier == 0.0:
                immune_members.append(member_name)
            elif multiplier < 1.0:
                resistant_members.append(member_name)
            elif multiplier > 1.0:
                weak_members.append(member_name)
            else:
                neutral_members.append(member_name)

        analysis[attacking_type] = TeamDefenseEntry(
            multipliers_by_member=multipliers_by_member,
            weak_members=tuple(weak_members),
            resistant_members=tuple(resistant_members),
            immune_members=tuple(immune_members),
            neutral_members=tuple(neutral_members),
        )

    return analysis


def summarize_team_weaknesses(
    analysis: Mapping[str, TeamDefenseEntry],
) -> list[TeamWeaknessSummary]:
    """Angriffstypen mit mindestens einer Teamschwäche sortiert zusammenfassen.

    Die Sortierung priorisiert:

    1. viele schwache Teammitglieder,
    2. wenige vorhandene Resistenzen oder Immunitäten,
    3. einen hohen maximalen Multiplikator,
    4. den Typnamen als deterministischen Gleichstandentscheid.

    Typen, gegen die kein Mitglied schwach ist, werden nicht aufgenommen.
    """
    summaries: list[TeamWeaknessSummary] = []

    for attacking_type, entry in analysis.items():
        weakness_count = len(entry["weak_members"])

        if weakness_count == 0:
            continue

        resistance_count = len(entry["resistant_members"])
        immunity_count = len(entry["immune_members"])

        summaries.append(
            TeamWeaknessSummary(
                attacking_type=attacking_type,
                weakness_count=weakness_count,
                resistance_count=resistance_count,
                immunity_count=immunity_count,
                neutral_count=len(entry["neutral_members"]),
                maximum_multiplier=max(
                    entry["multipliers_by_member"].values(),
                    default=1.0,
                ),
                weak_members=entry["weak_members"],
            )
        )

    summaries.sort(
        key=lambda summary: (
            -summary["weakness_count"],
            summary["resistance_count"] + summary["immunity_count"],
            -summary["maximum_multiplier"],
            summary["attacking_type"],
        )
    )

    return summaries
