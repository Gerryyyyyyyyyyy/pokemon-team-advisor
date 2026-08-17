"""Evolutionsmerkmale aus normalisierten Pokémon-Speziesdaten ableiten.

Dieses Modul enthält zunächst bewusst keinen Netzwerkzugriff. Die PokéAPI-Daten
werden später separat gesammelt und validiert. Hier verarbeiten wir nur die daraus
entstandenen Beziehungen zwischen Pokémon-Spezies.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict, cast

import httpx

type JsonObject = dict[str, object]


class SpeciesEvolutionData(TypedDict):
    """Die für Evolutionsmerkmale benötigten Angaben einer Spezies."""

    name: str
    evolves_from: str | None
    evolution_chain_id: int
    generation: int


class EvolutionFeatures(TypedDict):
    """Abgeleitete Evolutionsmerkmale für den Processed-Datensatz."""

    evolution_chain_id: int
    evolution_family: str
    evolution_stage: int
    evolution_max_stage: int
    is_final_evolution: bool
    generation: int


def _require_object(value: object, *, field: str) -> JsonObject:
    """Einen Wert als JSON-Objekt validieren."""
    if not isinstance(value, dict):
        raise ValueError(f"Field '{field}' must be a JSON object.")

    return cast(JsonObject, value)


def _require_string(value: object, *, field: str) -> str:
    """Einen nicht leeren String validieren."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty string.")

    return value


def _resource_id_from_url(
    value: object,
    *,
    endpoint: str,
    field: str,
) -> int:
    """Eine positive Ressourcen-ID aus einer PokéAPI-URL extrahieren."""
    resource_url = _require_string(value, field=field)
    path_parts = httpx.URL(resource_url).path.strip("/").split("/")

    # Der vorletzte Teil identifiziert den erwarteten Endpunkt, der letzte die ID.
    # So akzeptieren wir nicht versehentlich beispielsweise eine Pokémon-ID als
    # Evolutionsketten-ID.
    if len(path_parts) < 2 or path_parts[-2] != endpoint:
        raise ValueError(f"Field '{field}' has an unexpected resource URL.")

    try:
        resource_id = int(path_parts[-1])
    except ValueError as error:
        raise ValueError(f"Field '{field}' resource URL has no numeric ID.") from error

    if resource_id <= 0:
        raise ValueError(f"Field '{field}' resource ID must be positive.")

    return resource_id


def parse_species_evolution_data(payload: JsonObject) -> SpeciesEvolutionData:
    """Eine Pokémon-Species-Antwort auf Evolutionsangaben reduzieren.

    PokéAPI liefert deutlich mehr Speziesmerkmale, als wir für die aktuelle
    Fragestellung benötigen. Diese Funktion validiert und übernimmt nur Name,
    direkten Vorgänger, Evolutionsketten-ID und Einführungsgeneration.
    """
    name = _require_string(payload.get("name"), field="name")

    raw_parent = payload.get("evolves_from_species")
    if raw_parent is None:
        evolves_from = None
    else:
        parent = _require_object(raw_parent, field="evolves_from_species")
        evolves_from = _require_string(
            parent.get("name"),
            field="evolves_from_species.name",
        )

    evolution_chain = _require_object(
        payload.get("evolution_chain"),
        field="evolution_chain",
    )
    evolution_chain_id = _resource_id_from_url(
        evolution_chain.get("url"),
        endpoint="evolution-chain",
        field="evolution_chain.url",
    )

    generation = _require_object(payload.get("generation"), field="generation")
    generation_id = _resource_id_from_url(
        generation.get("url"),
        endpoint="generation",
        field="generation.url",
    )

    return SpeciesEvolutionData(
        name=name,
        evolves_from=evolves_from,
        evolution_chain_id=evolution_chain_id,
        generation=generation_id,
    )


def load_species_evolution_data(
    raw_directory: Path,
) -> list[SpeciesEvolutionData]:
    """Alle gecachten Species-Antworten eines Verzeichnisses einlesen.

    Die sortierten Dateinamen machen die Verarbeitung reproduzierbar. Inhaltlich
    verlassen wir uns trotzdem auf die Werte im JSON und nicht auf den Dateinamen.
    """
    if not raw_directory.is_dir():
        raise FileNotFoundError(f"Raw species directory does not exist: {raw_directory}")

    species_records: list[SpeciesEvolutionData] = []
    for path in sorted(raw_directory.glob("*.json")):
        raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
        payload = _require_object(raw_payload, field=str(path))
        species_records.append(parse_species_evolution_data(payload))

    return species_records


def prepare_evolution_directory(
    raw_directory: Path,
) -> dict[str, EvolutionFeatures]:
    """Species-Rohdaten laden und Evolutionsmerkmale je Name berechnen."""
    species_records = load_species_evolution_data(raw_directory)
    return build_evolution_features(species_records)


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
        ValueError: Bei doppelten Spezies, fehlenden Vorgängern oder einem Zyklus
            in den Evolutionsbeziehungen.
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

        if parent_name not in records_by_name:
            raise ValueError(f"Missing evolution parent '{parent_name}' for species '{name}'.")

        children_by_name[parent_name].add(name)

    stages_by_name: dict[str, int] = {}
    family_by_name: dict[str, str] = {}
    currently_resolving: set[str] = set()

    def resolve_stage_and_family(name: str) -> tuple[int, str]:
        """Stufe und Wurzel rekursiv bestimmen und Ergebnisse cachen."""
        cached_stage = stages_by_name.get(name)
        if cached_stage is not None:
            return cached_stage, family_by_name[name]

        # Treffen wir beim Folgen der Vorgänger erneut auf denselben Namen,
        # enthält die Eingabe einen fachlich unmöglichen Zyklus.
        if name in currently_resolving:
            raise ValueError(f"Evolution relationships contain a cycle at '{name}'.")

        currently_resolving.add(name)
        parent_name = records_by_name[name]["evolves_from"]

        if parent_name is None:
            stage = 0
            family = name
        else:
            parent_stage, family = resolve_stage_and_family(parent_name)
            stage = parent_stage + 1

        currently_resolving.remove(name)
        stages_by_name[name] = stage
        family_by_name[name] = family
        return stage, family

    for name in records_by_name:
        resolve_stage_and_family(name)

    # Die normalisierte Familie folgt den tatsächlichen Vorgängerbeziehungen. Das
    # ist nötig, weil PokéAPI in Sonderfällen wie Meltan/Melmetal unterschiedliche
    # evolution_chain-IDs liefert, obwohl evolves_from_species beide verbindet.
    max_stage_by_family: dict[str, int] = {}
    for name, stage in stages_by_name.items():
        family = family_by_name[name]
        previous_maximum = max_stage_by_family.get(family, 0)
        max_stage_by_family[family] = max(previous_maximum, stage)

    features_by_name: dict[str, EvolutionFeatures] = {}
    for name, record in records_by_name.items():
        chain_id = record["evolution_chain_id"]
        features_by_name[name] = EvolutionFeatures(
            evolution_chain_id=chain_id,
            evolution_family=family_by_name[name],
            evolution_stage=stages_by_name[name],
            evolution_max_stage=max_stage_by_family[family_by_name[name]],
            is_final_evolution=not children_by_name[name],
            generation=record["generation"],
        )

    return features_by_name
