"""Typeneffektivität aus PokéAPI-Daten aufbereiten und berechnen."""

import csv
import json
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

type JsonObject = dict[str, object]

# Die äußere Zuordnung enthält den angreifenden Typ.
# Die innere Zuordnung enthält den verteidigenden Typ und den Multiplikator.
#
# Beispiel:
# chart["fire"]["grass"] == 2.0
type TypeChart = Mapping[str, Mapping[str, float]]

# Eine einzelne Typbeziehung darf nur einen dieser Werte besitzen.
# Multiplikatoren wie 0.25 oder 4.0 entstehen erst durch zwei Verteidigertypen.
VALID_SINGLE_TYPE_MULTIPLIERS = frozenset({0.0, 0.5, 1.0, 2.0})

# PokéAPI listet nur nicht-neutrale Beziehungen auf. Die Namen der drei
# offensiven Listen werden hier zentral auf ihren Multiplikator abgebildet.
OFFENSIVE_RELATION_MULTIPLIERS = {
    "no_damage_to": 0.0,
    "half_damage_to": 0.5,
    "double_damage_to": 2.0,
}


def _require_object(value: object, *, field: str) -> JsonObject:
    """Einen Wert als JSON-Objekt validieren."""
    if not isinstance(value, dict):
        raise ValueError(f"Field '{field}' must be a JSON object.")

    return cast(JsonObject, value)


def _require_list(value: object, *, field: str) -> list[object]:
    """Einen Wert als JSON-Liste validieren."""
    if not isinstance(value, list):
        raise ValueError(f"Field '{field}' must be a JSON list.")

    return cast(list[object], value)


def _require_string(value: object, *, field: str) -> str:
    """Einen nicht leeren String validieren."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty string.")

    return value


def prepare_type_row(
    payload: JsonObject,
    *,
    supported_types: Collection[str],
) -> tuple[str, dict[str, float]]:
    """Eine PokéAPI-Type-Antwort in eine vollständige Matrixzeile umwandeln.

    PokéAPI nennt nur Immunitäten, Resistenzen und Schwächen ausdrücklich.
    Alle anderen unterstützten Typen werden deshalb zunächst als neutral
    mit dem Multiplikator ``1.0`` eingetragen.

    Beziehungen zu Typen außerhalb unseres MVP werden ignoriert. Dadurch können
    PokéAPI-Sondertypen verarbeitet werden, ohne sie in die Kampfmatrix der
    18 regulären Pokémon-Typen aufzunehmen.

    Args:
        payload: Unveränderte JSON-Antwort des PokéAPI-Type-Endpunkts.
        supported_types: Die Typen, die Teil unserer Matrix sein sollen.

    Returns:
        Ein Tupel aus angreifendem Typ und vollständiger Matrixzeile.

    Raises:
        ValueError: Wenn benötigte Felder fehlen, der angreifende Typ nicht
            unterstützt wird oder ein Verteidigertyp widersprüchlich in mehreren
            Schadenskategorien vorkommt.
    """
    if not supported_types:
        raise ValueError("Supported types must not be empty.")

    attacking_type = _require_string(payload.get("name"), field="name")

    if attacking_type not in supported_types:
        raise ValueError(f"Unsupported attacking type: {attacking_type}.")

    # Sortieren sorgt für eine reproduzierbare Reihenfolge, selbst wenn ein set
    # oder frozenset übergeben wurde.
    row = {defending_type: 1.0 for defending_type in sorted(supported_types)}

    damage_relations = _require_object(
        payload.get("damage_relations"),
        field="damage_relations",
    )

    # Damit erkennen wir sowohl doppelte Einträge innerhalb einer Liste als auch
    # widersprüchliche Zuordnungen zu zwei verschiedenen Schadenskategorien.
    assigned_defending_types: set[str] = set()

    for relation_name, multiplier in OFFENSIVE_RELATION_MULTIPLIERS.items():
        raw_relations = _require_list(
            damage_relations.get(relation_name),
            field=f"damage_relations.{relation_name}",
        )

        for index, raw_relation in enumerate(raw_relations):
            relation = _require_object(
                raw_relation,
                field=f"damage_relations.{relation_name}[{index}]",
            )
            defending_type = _require_string(
                relation.get("name"),
                field=f"damage_relations.{relation_name}[{index}].name",
            )

            # Manche PokéAPI-Typen gehören bewusst nicht zum aktuellen MVP.
            if defending_type not in supported_types:
                continue

            if defending_type in assigned_defending_types:
                raise ValueError(
                    f"Defending type '{defending_type}' appears in multiple damage relations."
                )

            assigned_defending_types.add(defending_type)
            row[defending_type] = multiplier

    return attacking_type, row


def build_type_chart(
    payloads: Iterable[JsonObject],
    *,
    supported_types: Collection[str],
) -> dict[str, dict[str, float]]:
    """Mehrere PokéAPI-Type-Antworten zu einer quadratischen Matrix verbinden.

    Für jeden unterstützten Typ muss genau eine API-Antwort vorhanden sein.
    Dadurch verhindern wir, dass eine unvollständige Matrix später neutrale
    Beziehungen vortäuscht.

    Args:
        payloads: Unveränderte Antworten des PokéAPI-Type-Endpunkts.
        supported_types: Typen, die sowohl als Angreifer als auch als
            Verteidiger in der Matrix vorkommen müssen.

    Returns:
        Die vollständige Matrix in der Form
        ``chart[angreifender_typ][verteidigender_typ]``.

    Raises:
        ValueError: Wenn kein Typ angegeben wurde, ein Angriffstyp doppelt
            vorkommt oder mindestens eine benötigte Zeile fehlt.
    """
    supported_type_set = frozenset(supported_types)

    if not supported_type_set:
        raise ValueError("Supported types must not be empty.")

    chart: dict[str, dict[str, float]] = {}

    for payload in payloads:
        attacking_type, row = prepare_type_row(
            payload,
            supported_types=supported_type_set,
        )

        if attacking_type in chart:
            raise ValueError(f"Duplicate attacking type: {attacking_type}.")

        chart[attacking_type] = row

    missing_types = supported_type_set.difference(chart)

    if missing_types:
        missing = ", ".join(sorted(missing_types))
        raise ValueError(f"Missing attacking types: {missing}.")

    # Die alphabetische Reihenfolge macht das Ergebnis unabhängig von der
    # Reihenfolge der Dateien oder API-Antworten.
    return {attacking_type: chart[attacking_type] for attacking_type in sorted(chart)}


def load_type_payloads(raw_directory: Path) -> list[JsonObject]:
    """Alle gecachten Type-Antworten sortiert laden und Dateinamen prüfen.

    Der Dateiname ist Teil unserer Raw-Cache-Konvention. ``fire.json`` muss deshalb
    auch eine Type-Ressource mit ``name == "fire"`` enthalten. Die Prüfung erkennt
    vertauschte oder manuell falsch benannte Cache-Dateien frühzeitig.
    """
    if not raw_directory.is_dir():
        raise FileNotFoundError(f"Raw type directory does not exist: {raw_directory}")

    payloads: list[JsonObject] = []

    for path in sorted(raw_directory.glob("*.json")):
        raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
        payload = _require_object(raw_payload, field=str(path))
        type_name = _require_string(payload.get("name"), field=f"{path}.name")

        if path.stem != type_name:
            raise ValueError(
                f"Type cache filename does not match payload name: '{path.stem}' != '{type_name}'."
            )

        payloads.append(payload)

    return payloads


def prepare_type_directory(
    raw_directory: Path,
    *,
    supported_types: Collection[str],
) -> dict[str, dict[str, float]]:
    """Ein Raw-Verzeichnis laden und daraus die aktuelle Typenmatrix erzeugen."""
    payloads = load_type_payloads(raw_directory)
    return build_type_chart(payloads, supported_types=supported_types)


def _validated_chart_type_names(chart: TypeChart) -> list[str]:
    """Eine quadratische Matrix prüfen und ihre sortierten Typnamen liefern."""
    if not chart:
        raise ValueError("Type chart must not be empty.")

    type_names = sorted(chart)
    expected_types = set(type_names)

    for attacking_type in type_names:
        row = chart[attacking_type]
        actual_types = set(row)

        if actual_types != expected_types:
            missing = ", ".join(sorted(expected_types.difference(actual_types)))
            unexpected = ", ".join(sorted(actual_types.difference(expected_types)))
            raise ValueError(
                f"Type chart row '{attacking_type}' is not square; "
                f"missing=[{missing}], unexpected=[{unexpected}]."
            )

        for defending_type, multiplier in row.items():
            if multiplier not in VALID_SINGLE_TYPE_MULTIPLIERS:
                raise ValueError(
                    "Invalid type chart multiplier for "
                    f"'{attacking_type}' against '{defending_type}': {multiplier}."
                )

    return type_names


def write_type_chart_csv(
    chart: TypeChart,
    *,
    output_path: Path,
) -> Path:
    """Eine validierte Typenmatrix deterministisch und atomar als CSV schreiben.

    Die erste Spalte enthält den angreifenden Typ. Alle weiteren Spalten sind die
    verteidigenden Typen in alphabetischer Reihenfolge.
    """
    type_names = _validated_chart_type_names(chart)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    with temporary_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["attacking_type", *type_names])

        for attacking_type in type_names:
            row = chart[attacking_type]
            writer.writerow(
                [
                    attacking_type,
                    *(row[defending_type] for defending_type in type_names),
                ]
            )

    temporary_path.replace(output_path)
    return output_path


def prepare_type_dataset(
    *,
    raw_directory: Path,
    supported_types: Collection[str],
    output_path: Path,
) -> dict[str, dict[str, float]]:
    """Type-Rohdaten aufbereiten, als CSV speichern und die Matrix zurückgeben."""
    chart = prepare_type_directory(
        raw_directory,
        supported_types=supported_types,
    )
    write_type_chart_csv(chart, output_path=output_path)
    return chart


def calculate_type_multiplier(
    attacking_type: str,
    defending_types: Sequence[str],
    *,
    chart: TypeChart,
) -> float:
    """Den Schadensmultiplikator gegen ein Pokémon berechnen.

    Ein Pokémon besitzt einen oder zwei Typen. Bei zwei Typen werden die beiden
    einzelnen Multiplikatoren miteinander multipliziert.

    Beispiele:
        Feuer gegen Pflanze/Stahl:
        ``2.0 * 2.0 = 4.0``

        Boden gegen Elektro/Flug:
        ``2.0 * 0.0 = 0.0``

    Args:
        attacking_type: Typ des verwendeten Angriffs.
        defending_types: Ein oder zwei Typen des verteidigenden Pokémon.
        chart: Typenmatrix in der Form
            ``chart[angreifender_typ][verteidigender_typ]``.

    Returns:
        Den kombinierten Multiplikator.

    Raises:
        ValueError: Wenn Typen fehlen, doppelt vorkommen oder die Matrix einen
            ungültigen Multiplikator enthält.
    """
    if not attacking_type:
        raise ValueError("Attacking type must not be empty.")

    if len(defending_types) not in (1, 2):
        raise ValueError("A defender must have one or two types.")

    if len(set(defending_types)) != len(defending_types):
        raise ValueError("Defending types must be unique.")

    if attacking_type not in chart:
        raise ValueError(f"Unknown attacking type: {attacking_type}.")

    attacking_relations = chart[attacking_type]
    combined_multiplier = 1.0

    for defending_type in defending_types:
        if not defending_type:
            raise ValueError("Defending type must not be empty.")

        if defending_type not in attacking_relations:
            raise ValueError(
                f"Unknown defending type '{defending_type}' for attack type '{attacking_type}'."
            )

        single_multiplier = attacking_relations[defending_type]

        if single_multiplier not in VALID_SINGLE_TYPE_MULTIPLIERS:
            raise ValueError(f"Invalid single-type multiplier: {single_multiplier}.")

        combined_multiplier *= single_multiplier

    return combined_multiplier
