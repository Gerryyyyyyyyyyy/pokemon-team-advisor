"""Transparente Rollenprofile aus den sechs Pokémon-Basiswerten ableiten.

Die Rollenpassung beschreibt die relative Verteilung der Werte eines Pokémon.
Der getrennte Stärkewert beschreibt dagegen, wie hoch die für eine Rolle
relevanten absoluten Werte innerhalb der Referenzmenge liegen.
"""

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from math import sqrt
from numbers import Integral
from typing import TypedDict


class Role(StrEnum):
    """Unterstützte Rollen der regelbasierten Baseline."""

    PHYSICAL_ATTACKER = "physical_attacker"
    SPECIAL_ATTACKER = "special_attacker"
    FAST_ATTACKER = "fast_attacker"
    PHYSICAL_DEFENDER = "physical_defender"
    SPECIAL_DEFENDER = "special_defender"
    ALL_ROUNDER = "all_rounder"


class RoleScore(TypedDict):
    """Passung, Stärke und Vergabestatus für genau eine Rolle."""

    role: Role
    fit_score: float
    strength_score: float
    assigned: bool


class _PreparedPokemon(TypedDict):
    """Intern validierter und normalisierter Pokémon-Datensatz."""

    id: int
    name: str
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    base_stat_total: int


_STAT_FIELDS = (
    "hp",
    "attack",
    "defense",
    "special_attack",
    "special_defense",
    "speed",
)

# Näherung der Basiswerte auf Stufe 50 bei 31 IVs und null EVs. Die Offsets
# dienen nur einem stabileren Bulk-Vergleich; sie sind keine Schadensrechnung.
_HP_BULK_OFFSET = 75
_OTHER_BULK_OFFSET = 20
_MINIMUM_STRENGTH_SCORE = 0.4
_HIGH_STRENGTH_SCORE = 0.8
_HIGH_STRENGTH_FIT_FLOOR = 0.7


def _positive_integer(value: object, *, field: str) -> int:
    """Einen positiven ganzzahligen Wert akzeptieren und normalisieren."""
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"Field '{field}' must be a positive integer.")
    return int(value)


def _prepare_pokemon(
    pokemon: Iterable[Mapping[str, object]],
) -> list[_PreparedPokemon]:
    """Eingabedaten validieren, ohne die ursprünglichen Mappings zu verändern."""
    prepared: list[_PreparedPokemon] = []
    seen_ids: set[int] = set()

    for index, item in enumerate(pokemon):
        pokemon_id = _positive_integer(item.get("id"), field=f"pokemon[{index}].id")
        if pokemon_id in seen_ids:
            raise ValueError(f"Duplicate Pokemon id: {pokemon_id}.")
        seen_ids.add(pokemon_id)

        raw_name = item.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError(f"Field 'pokemon[{index}].name' must be a non-empty string.")

        stats = {
            field: _positive_integer(
                item.get(field),
                field=f"pokemon[{index}].{field}",
            )
            for field in _STAT_FIELDS
        }
        base_stat_total = _positive_integer(
            item.get("base_stat_total"),
            field=f"pokemon[{index}].base_stat_total",
        )
        if base_stat_total != sum(stats.values()):
            raise ValueError(f"Field 'pokemon[{index}].base_stat_total' must equal the six stats.")

        prepared.append(
            _PreparedPokemon(
                id=pokemon_id,
                name=raw_name.strip(),
                hp=stats["hp"],
                attack=stats["attack"],
                defense=stats["defense"],
                special_attack=stats["special_attack"],
                special_defense=stats["special_defense"],
                speed=stats["speed"],
                base_stat_total=base_stat_total,
            )
        )

    if not prepared:
        raise ValueError("Reference data must contain at least one Pokemon.")
    return prepared


def _fit_metrics(pokemon: _PreparedPokemon) -> dict[Role, float]:
    """Relative, von der absoluten Gesamtstärke getrennte Profilmaße bilden."""
    total = pokemon["base_stat_total"]
    stats = [
        pokemon["hp"],
        pokemon["attack"],
        pokemon["defense"],
        pokemon["special_attack"],
        pokemon["special_defense"],
        pokemon["speed"],
    ]
    balance = 1.0 - ((max(stats) - min(stats)) / max(stats))
    physical_bulk = _bulk_proxy(pokemon["hp"], pokemon["defense"])
    special_bulk = _bulk_proxy(pokemon["hp"], pokemon["special_defense"])

    return {
        Role.PHYSICAL_ATTACKER: pokemon["attack"] / total,
        Role.SPECIAL_ATTACKER: pokemon["special_attack"] / total,
        Role.FAST_ATTACKER: pokemon["speed"] / total,
        Role.PHYSICAL_DEFENDER: physical_bulk / total,
        Role.SPECIAL_DEFENDER: special_bulk / total,
        Role.ALL_ROUNDER: balance,
    }


def _bulk_proxy(hp: int, defensive_stat: int) -> float:
    """HP und einen Defensivwert ohne vollständige Kompensation verbinden."""
    return sqrt((hp + _HP_BULK_OFFSET) * (defensive_stat + _OTHER_BULK_OFFSET))


def _strength_metrics(pokemon: _PreparedPokemon) -> dict[Role, float]:
    """Für jede Rolle relevante absolute Werte zusammenfassen."""
    strongest_attack = max(pokemon["attack"], pokemon["special_attack"])
    return {
        Role.PHYSICAL_ATTACKER: float(pokemon["attack"]),
        Role.SPECIAL_ATTACKER: float(pokemon["special_attack"]),
        Role.FAST_ATTACKER: sqrt(pokemon["speed"] * strongest_attack),
        Role.PHYSICAL_DEFENDER: _bulk_proxy(pokemon["hp"], pokemon["defense"]),
        Role.SPECIAL_DEFENDER: _bulk_proxy(pokemon["hp"], pokemon["special_defense"]),
        Role.ALL_ROUNDER: float(pokemon["base_stat_total"]),
    }


def _percentile_ranks(values: Sequence[float]) -> list[float]:
    """Empirische Perzentilränge mit mittlerem Rang für Gleichstände berechnen."""
    indexed_values = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    start = 0

    while start < len(indexed_values):
        end = start + 1
        while end < len(indexed_values) and indexed_values[end][1] == indexed_values[start][1]:
            end += 1

        average_one_based_rank = ((start + 1) + end) / 2.0
        percentile = average_one_based_rank / len(indexed_values)
        for position in range(start, end):
            original_index = indexed_values[position][0]
            ranks[original_index] = percentile
        start = end

    return ranks


def _scaled_metrics(
    raw_metrics: Sequence[Mapping[Role, float]],
) -> list[dict[Role, float]]:
    """Jedes Rollenmaß getrennt auf empirische Perzentile skalieren."""
    scaled = [{role: 0.0 for role in Role} for _ in raw_metrics]
    for role in Role:
        role_ranks = _percentile_ranks([metrics[role] for metrics in raw_metrics])
        for index, rank in enumerate(role_ranks):
            scaled[index][role] = rank
    return scaled


def _assigned_roles(
    strength_scores: Mapping[Role, float],
    fit_scores: Mapping[Role, float],
    *,
    minimum_fit_score: float,
    maximum_roles: int,
) -> set[Role]:
    """Profil und Stärke anwenden, aber immer eine Primärrolle vergeben."""
    ordered_roles = sorted(
        Role,
        key=lambda role: (
            -(fit_scores[role] + strength_scores[role]),
            -fit_scores[role],
            role.value,
        ),
    )
    qualifying: list[Role] = []
    for role in ordered_roles:
        clear_profile = fit_scores[role] >= minimum_fit_score and (
            role is Role.ALL_ROUNDER or strength_scores[role] >= _MINIMUM_STRENGTH_SCORE
        )
        high_performance = (
            fit_scores[role] >= _HIGH_STRENGTH_FIT_FLOOR
            and strength_scores[role] >= _HIGH_STRENGTH_SCORE
        )
        if clear_profile or high_performance:
            qualifying.append(role)
    if not qualifying:
        qualifying = ordered_roles[:1]
    return set(qualifying[:maximum_roles])


def analyze_pokemon_roles(
    pokemon: Iterable[Mapping[str, object]],
    *,
    minimum_fit_score: float = 0.8,
    maximum_roles: int = 3,
) -> dict[int, tuple[RoleScore, ...]]:
    """Rollenpassung und Rollenstärke relativ zu einer Referenzmenge bewerten.

    Eine Rolle qualifiziert sich durch klare Spezialisierung mit mindestens
    moderater Stärke oder durch hohe Stärke bei guter Passung. Allrounder
    benötigen als reine Profilrolle keine Mindeststärke. Erfüllt keine Rolle
    diese Regeln, bleibt die insgesamt beste Rolle als Primärrolle erhalten.
    """
    if not 0.0 <= minimum_fit_score <= 1.0:
        raise ValueError("minimum_fit_score must be between zero and one.")
    if isinstance(maximum_roles, bool) or not 1 <= maximum_roles <= len(Role):
        raise ValueError(f"maximum_roles must be between 1 and {len(Role)}.")

    prepared = _prepare_pokemon(pokemon)
    fit_scores = _scaled_metrics([_fit_metrics(item) for item in prepared])
    strength_scores = _scaled_metrics([_strength_metrics(item) for item in prepared])

    analysis: dict[int, tuple[RoleScore, ...]] = {}
    for index, item in enumerate(prepared):
        assigned = _assigned_roles(
            strength_scores[index],
            fit_scores[index],
            minimum_fit_score=minimum_fit_score,
            maximum_roles=maximum_roles,
        )
        analysis[item["id"]] = tuple(
            RoleScore(
                role=role,
                fit_score=fit_scores[index][role],
                strength_score=strength_scores[index][role],
                assigned=role in assigned,
            )
            for role in Role
        )
    return analysis
