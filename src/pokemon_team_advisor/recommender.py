"""Nachvollziehbare Empfehlungen für das sechste Mitglied eines Pokémon-Teams."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isclose, isfinite, isnan, log2
from numbers import Integral, Real
from typing import TypedDict

from pokemon_team_advisor.roles import Role, RoleScore, analyze_pokemon_roles
from pokemon_team_advisor.type_effectiveness import (
    TypeChart,
    calculate_type_multiplier,
)


class Recommendation(TypedDict):
    """Ein Kandidat mit Gesamtscore und erklärbaren Teilwerten."""

    pokemon_id: int
    name: str
    total_score: float
    defensive_score: float
    role_score: float
    strength_score: float
    matched_roles: tuple[Role, ...]
    covered_threats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecommendationWeights:
    """Gewichte der drei normalisierten Empfehlungsbestandteile."""

    defensive: float = 0.5
    role: float = 0.3
    strength: float = 0.2

    def __post_init__(self) -> None:
        """Nur endliche, nicht negative Gewichte mit Summe eins erlauben."""
        weights = (self.defensive, self.role, self.strength)
        if any(not isfinite(weight) or weight < 0.0 for weight in weights):
            raise ValueError("Recommendation weights must be finite and non-negative.")

        if not isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("Recommendation weights must sum to 1.0.")


DEFAULT_RECOMMENDATION_WEIGHTS = RecommendationWeights()


def _require_positive_int(value: object, *, field: str) -> int:
    """Einen positiven ganzzahligen Bezeichner validieren."""
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"Field '{field}' must be a positive integer.")
    return int(value)


def _require_non_empty_string(value: object, *, field: str) -> str:
    """Einen nicht leeren String validieren."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty string.")
    return value


def _optional_type(value: object, *, field: str) -> str | None:
    """Einen optionalen Typ lesen und numerische NaN-Werte als fehlend behandeln."""
    if value is None:
        return None

    if isinstance(value, Real) and not isinstance(value, bool):
        numeric_value = float(value)
        if isnan(numeric_value):
            return None

    return _require_non_empty_string(value, field=field)


def _require_bool(value: object, *, field: str) -> bool:
    """Einen booleschen Wert validieren."""
    if not isinstance(value, bool):
        raise ValueError(f"Field '{field}' must be a boolean.")
    return value


def _prepare_pokemon(
    pokemon: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Benötigte Felder normalisieren, ohne Eingabedatensätze zu verändern."""
    prepared: list[dict[str, object]] = []
    seen_ids: set[int] = set()

    for index, item in enumerate(pokemon):
        pokemon_id = _require_positive_int(item.get("id"), field=f"pokemon[{index}].id")
        if pokemon_id in seen_ids:
            raise ValueError(f"Duplicate Pokémon id: {pokemon_id}.")
        seen_ids.add(pokemon_id)

        name = _require_non_empty_string(item.get("name"), field=f"pokemon[{index}].name")
        type_1 = _require_non_empty_string(item.get("type_1"), field=f"pokemon[{index}].type_1")
        type_2 = _optional_type(item.get("type_2"), field=f"pokemon[{index}].type_2")
        if type_2 == type_1:
            raise ValueError("A Pokémon must not have duplicate types.")

        is_final_evolution = _require_bool(
            item.get("is_final_evolution"),
            field=f"pokemon[{index}].is_final_evolution",
        )

        normalized = dict(item)
        normalized.update(
            id=pokemon_id,
            name=name,
            type_1=type_1,
            type_2=type_2,
            is_final_evolution=is_final_evolution,
        )
        prepared.append(normalized)

    if not prepared:
        raise ValueError("Pokémon data must not be empty.")

    return prepared


def _prepare_team_ids(team_ids: Sequence[int]) -> tuple[int, ...]:
    """Genau fünf eindeutige Team-IDs verlangen."""
    prepared = tuple(
        _require_positive_int(value, field=f"team_ids[{index}]")
        for index, value in enumerate(team_ids)
    )
    if len(prepared) != 5 or len(set(prepared)) != 5:
        raise ValueError("Team must contain exactly five unique Pokémon ids.")
    return prepared


def _defending_types(pokemon: Mapping[str, object]) -> tuple[str, ...]:
    """Die bereits validierten Typen eines Pokémon zurückgeben."""
    type_1 = str(pokemon["type_1"])
    type_2 = pokemon["type_2"]
    if type_2 is None:
        return (type_1,)
    return type_1, str(type_2)


def _team_threat_weights(
    team: Sequence[Mapping[str, object]],
    *,
    chart: TypeChart,
) -> dict[str, float]:
    """Gemeinsame Schwächen gewichten; 4x-Schwächen zählen stärker als 2x."""
    if not chart:
        raise ValueError("Type chart must not be empty.")

    threats: dict[str, float] = {}
    for attacking_type in sorted(chart):
        threat_weight = 0.0
        for member in team:
            multiplier = calculate_type_multiplier(
                attacking_type,
                _defending_types(member),
                chart=chart,
            )
            threat_weight += max(0.0, multiplier - 1.0)

        if threat_weight > 0.0:
            threats[attacking_type] = threat_weight

    return threats


def _defensive_response(multiplier: float) -> float:
    """Einen defensiven Multiplikator auf einen Wert zwischen null und eins abbilden."""
    if multiplier == 0.0:
        return 1.0
    return min(1.0, max(0.0, (2.0 - log2(multiplier)) / 4.0))


def _defensive_fit(
    candidate: Mapping[str, object],
    *,
    chart: TypeChart,
    threats: Mapping[str, float],
) -> tuple[float, tuple[str, ...]]:
    """Defensive Ergänzung und konkret abgedeckte Teamgefahren berechnen."""
    candidate_types = _defending_types(candidate)

    # Ein Team ohne aktuelle Schwäche wird gegen die gesamte Matrix bewertet.
    # So bleibt eine Immunität oder Resistenz auch dort aussagekräftiger als
    # eine zusätzliche Schwäche, während Neutralität genau 0.5 ergibt.
    score_weights: Mapping[str, float]
    if threats:
        score_weights = threats
    else:
        score_weights = {attacking_type: 1.0 for attacking_type in sorted(chart)}

    weighted_score = 0.0
    total_weight = 0.0
    covered: list[str] = []
    multipliers: dict[str, float] = {}

    for attacking_type, weight in score_weights.items():
        multiplier = calculate_type_multiplier(
            attacking_type,
            candidate_types,
            chart=chart,
        )
        multipliers[attacking_type] = multiplier
        weighted_score += weight * _defensive_response(multiplier)
        total_weight += weight

    for attacking_type in threats:
        covered_multiplier = multipliers.get(attacking_type)
        if covered_multiplier is None:
            covered_multiplier = calculate_type_multiplier(
                attacking_type,
                candidate_types,
                chart=chart,
            )
        if covered_multiplier < 1.0:
            covered.append(attacking_type)

    covered.sort(key=lambda attacking_type: (-threats[attacking_type], attacking_type))
    return weighted_score / total_weight, tuple(covered)


def _effective_role_score(role_score: RoleScore) -> float:
    """Profilpassung und absolute Rollenstärke gemeinsam berücksichtigen."""
    return float(role_score["fit_score"]) * float(role_score["strength_score"])


def _team_role_coverage(
    team_ids: Sequence[int],
    *,
    roles_by_id: Mapping[int, tuple[RoleScore, ...]],
) -> dict[Role, float]:
    """Beste bereits vorhandene Besetzung jeder Rolle bestimmen."""
    coverage = {role: 0.0 for role in Role}
    for pokemon_id in team_ids:
        for score in roles_by_id[pokemon_id]:
            if not score["assigned"]:
                continue
            role = score["role"]
            coverage[role] = max(coverage[role], _effective_role_score(score))
    return coverage


def _role_fit(
    candidate_roles: Sequence[RoleScore],
    *,
    team_coverage: Mapping[Role, float],
) -> tuple[float, tuple[Role, ...]]:
    """Bewerten, wie gut ein Kandidat noch offene Teamrollen schließt."""
    contributions: list[tuple[float, Role]] = []
    for score in candidate_roles:
        if score["assigned"]:
            role = score["role"]
            contribution = _effective_role_score(score) * (1.0 - team_coverage[role])
            contributions.append((contribution, role))

    # analyze_pokemon_roles weist auch schwachen Pokémon mindestens ihr klarstes
    # Profil zu. Die Absicherung hält die öffentliche API trotzdem robust.
    if not contributions:
        best = max(candidate_roles, key=_effective_role_score)
        role = best["role"]
        contributions.append((_effective_role_score(best) * (1.0 - team_coverage[role]), role))

    contributions.sort(key=lambda item: (-item[0], item[1].value))
    best_contribution = contributions[0][0]
    secondary_contributions = sum(value for value, _ in contributions[1:])
    normalized_score = min(1.0, best_contribution + 0.25 * secondary_contributions)
    matched_roles = tuple(role for _, role in contributions)
    return normalized_score, matched_roles


def _overall_strength(candidate_roles: Sequence[RoleScore]) -> float:
    """Den rollenunabhängigen Stärkewert aus dem Allrounder-Profil lesen."""
    for score in candidate_roles:
        if score["role"] is Role.ALL_ROUNDER:
            return float(score["strength_score"])
    raise ValueError("Role analysis does not contain an all-rounder score.")


def recommend_team_members(
    team_ids: Sequence[int],
    pokemon: Iterable[Mapping[str, object]],
    *,
    chart: TypeChart,
    weights: RecommendationWeights = DEFAULT_RECOMMENDATION_WEIGHTS,
    limit: int = 5,
    include_non_final: bool = False,
) -> list[Recommendation]:
    """Passende sechste Teammitglieder sortiert und erklärbar empfehlen.

    Standardmäßig werden nur finale Entwicklungen berücksichtigt. Vor- und
    Zwischenentwicklungen lassen sich für Spezialfälle explizit einschalten.
    """
    if isinstance(limit, bool) or not isinstance(limit, Integral) or limit <= 0:
        raise ValueError("Recommendation limit must be a positive integer.")
    if not isinstance(include_non_final, bool):
        raise ValueError("include_non_final must be a boolean.")
    if not isinstance(weights, RecommendationWeights):
        raise TypeError("weights must be a RecommendationWeights instance.")

    prepared_team_ids = _prepare_team_ids(team_ids)
    prepared_pokemon = _prepare_pokemon(pokemon)
    pokemon_by_id = {int(item["id"]): item for item in prepared_pokemon}

    for pokemon_id in prepared_team_ids:
        if pokemon_id not in pokemon_by_id:
            raise ValueError(f"Unknown team member id: {pokemon_id}")

    roles_by_id = analyze_pokemon_roles(prepared_pokemon)
    team = [pokemon_by_id[pokemon_id] for pokemon_id in prepared_team_ids]
    threats = _team_threat_weights(team, chart=chart)
    team_coverage = _team_role_coverage(
        prepared_team_ids,
        roles_by_id=roles_by_id,
    )
    team_id_set = set(prepared_team_ids)

    recommendations: list[Recommendation] = []
    for candidate in prepared_pokemon:
        pokemon_id = int(candidate["id"])
        if pokemon_id in team_id_set:
            continue
        if not include_non_final and not bool(candidate["is_final_evolution"]):
            continue

        candidate_roles = roles_by_id[pokemon_id]
        defensive_score, covered_threats = _defensive_fit(
            candidate,
            chart=chart,
            threats=threats,
        )
        role_score, matched_roles = _role_fit(
            candidate_roles,
            team_coverage=team_coverage,
        )
        strength_score = _overall_strength(candidate_roles)
        total_score = 100.0 * (
            weights.defensive * defensive_score
            + weights.role * role_score
            + weights.strength * strength_score
        )

        recommendations.append(
            Recommendation(
                pokemon_id=pokemon_id,
                name=str(candidate["name"]),
                total_score=total_score,
                defensive_score=defensive_score,
                role_score=role_score,
                strength_score=strength_score,
                matched_roles=matched_roles,
                covered_threats=covered_threats,
            )
        )

    recommendations.sort(
        key=lambda recommendation: (
            -recommendation["total_score"],
            -recommendation["defensive_score"],
            -recommendation["role_score"],
            -recommendation["strength_score"],
            recommendation["name"],
            recommendation["pokemon_id"],
        )
    )
    return recommendations[: int(limit)]
