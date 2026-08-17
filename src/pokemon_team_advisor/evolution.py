"""Evolutionsmerkmale aus normalisierten Pokémon-Speziesdaten ableiten.

Dieses Modul enthält zunächst bewusst keinen Netzwerkzugriff. Die PokéAPI-Daten
werden später separat gesammelt und validiert. Hier verarbeiten wir nur die daraus
entstandenen Beziehungen zwischen Pokémon-Spezies.
"""

from collections.abc import Iterable
from typing import TypedDict


class SpeciesEvolutionData(TypedDict):
    """Die für Evolutionsmerkmale benötigten Angaben einer Spezies."""

    name: str
    evolves_from: str | None
    evolution_chain_id: int
    generation: int


class EvolutionFeatures(TypedDict):
    """Abgeleitete Evolutionsmerkmale für den Processed-Datensatz."""

    evolution_chain_id: int
    evolution_stage: int
    evolution_max_stage: int
    is_final_evolution: bool
    generation: int


def build_evolution_features(
    species_records: Iterable[SpeciesEvolutionData],
) -> dict[str, EvolutionFeatures]:
    """Evolutionsmerkmale je Speziesname berechnen.

    Die Stufe entspricht der Anzahl der Schritte von der Wurzel der Kette zur
    Spezies. Eine Wurzel erhält Stufe 0, ihre direkte Entwicklung Stufe 1 usw.

    Args:
        species_records: Normalisierte Spezies mit direktem Vorgänger und
            Evolutionsketten-ID.

    Returns:
        Ein Dictionary, das jeden Speziesnamen auf seine Merkmale abbildet.

    Raises:
        ValueError: Bei doppelten Spezies, fehlenden Vorgängern, widersprüchlichen
            Ketten-IDs oder einem Zyklus in den Evolutionsbeziehungen.
    """
    records_by_name: dict[str, SpeciesEvolutionData] = {}

    # Die Eingabe wird zuerst vollständig materialisiert. Dadurch können wir alle
    # Vorgänger prüfen, bevor die eigentliche Stufenberechnung beginnt.
    for record in species_records:
        name = record["name"]
        if name in records_by_name:
            raise ValueError(f"Duplicate Pokémon species: {name}.")

        records_by_name[name] = record

    children_by_name: dict[str, set[str]] = {name: set() for name in records_by_name}

    # Aus den Vorgänger-Beziehungen bauen wir zusätzlich die Kind-Beziehungen.
    # Eine Spezies ohne Kinder ist später eine finale Entwicklung.
    for name, record in records_by_name.items():
        parent_name = record["evolves_from"]
        if parent_name is None:
            continue

        parent = records_by_name.get(parent_name)
        if parent is None:
            raise ValueError(f"Missing evolution parent '{parent_name}' for species '{name}'.")

        if parent["evolution_chain_id"] != record["evolution_chain_id"]:
            raise ValueError(f"Evolution chain mismatch between '{parent_name}' and '{name}'.")

        children_by_name[parent_name].add(name)

    stages_by_name: dict[str, int] = {}
    currently_resolving: set[str] = set()

    def resolve_stage(name: str) -> int:
        """Die Stufe rekursiv bestimmen und bereits berechnete Werte cachen."""
        cached_stage = stages_by_name.get(name)
        if cached_stage is not None:
            return cached_stage

        # Treffen wir beim Folgen der Vorgänger erneut auf denselben Namen,
        # enthält die Eingabe einen fachlich unmöglichen Zyklus.
        if name in currently_resolving:
            raise ValueError(f"Evolution relationships contain a cycle at '{name}'.")

        currently_resolving.add(name)
        parent_name = records_by_name[name]["evolves_from"]

        if parent_name is None:
            stage = 0
        else:
            stage = resolve_stage(parent_name) + 1

        currently_resolving.remove(name)
        stages_by_name[name] = stage
        return stage

    for name in records_by_name:
        resolve_stage(name)

    # Alle Mitglieder derselben Kette erhalten dieselbe maximale Kettenstufe.
    # Bei verzweigten Ketten ist dies die tiefste vorhandene Entwicklung.
    max_stage_by_chain: dict[int, int] = {}
    for name, stage in stages_by_name.items():
        chain_id = records_by_name[name]["evolution_chain_id"]
        previous_maximum = max_stage_by_chain.get(chain_id, 0)
        max_stage_by_chain[chain_id] = max(previous_maximum, stage)

    features_by_name: dict[str, EvolutionFeatures] = {}
    for name, record in records_by_name.items():
        chain_id = record["evolution_chain_id"]
        features_by_name[name] = EvolutionFeatures(
            evolution_chain_id=chain_id,
            evolution_stage=stages_by_name[name],
            evolution_max_stage=max_stage_by_chain[chain_id],
            is_final_evolution=not children_by_name[name],
            generation=record["generation"],
        )

    return features_by_name
