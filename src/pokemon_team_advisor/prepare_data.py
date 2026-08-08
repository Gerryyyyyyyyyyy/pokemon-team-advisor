"""PokéAPI-Rohdaten in eine flache, analysierbare Tabelle überführen.

``collect_data.py`` ist für Netzwerk und Rohdaten-Cache zuständig. Dieses Modul
beginnt bewusst erst danach: Es liest die unveränderten JSON-Dateien, filtert auf
Standardformen und extrahiert genau die Merkmale, die unser MVP benötigt.

Die Trennung ist für ein Data-Science-Projekt wichtig: Rohdaten bleiben als
reproduzierbare Quelle erhalten, während sich die fachliche Transformation später
ändern darf, ohne die API erneut aufrufen zu müssen.
"""

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict, cast

# Diese sechs Werte bilden das Stat-Schema unseres MVP. Wir greifen später über den
# Namen darauf zu und nicht über die Position in der PokéAPI-Liste. Dadurch wäre
# beispielsweise eine andere Reihenfolge der API-Antwort kein Datenfehler.
EXPECTED_STAT_NAMES = frozenset(
    {
        "hp",
        "attack",
        "defense",
        "special-attack",
        "special-defense",
        "speed",
    }
)

# Die CSV-Spalten stehen an einer zentralen Stelle. Dadurch bleiben Reihenfolge und
# Ausgabe deterministisch und müssen nicht aus einem Dictionary abgeleitet werden.
PROCESSED_COLUMNS = (
    "id",
    "name",
    "is_default",
    "type_1",
    "type_2",
    "hp",
    "attack",
    "defense",
    "special_attack",
    "special_defense",
    "speed",
    "base_stat_total",
    "sprite_url",
)

type JsonObject = dict[str, object]


class PokemonRecord(TypedDict):
    """Das flache Datenschema eines Standard-Pokémon im MVP.

    ``TypedDict`` gibt uns die Lesbarkeit eines normalen Dictionaries, lässt mypy
    aber trotzdem kontrollieren, ob Schlüssel und Werttypen stimmen. Das passt hier
    besser als eine große Modellklasse, weil die Daten später tabellarisch werden.
    """

    id: int
    name: str
    is_default: bool
    type_1: str
    type_2: str | None
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    base_stat_total: int
    sprite_url: str | None


def _require_object(value: object, *, field: str) -> JsonObject:
    """Einen Wert als JSON-Objekt validieren und typisiert zurückgeben."""
    if not isinstance(value, dict):
        raise ValueError(f"Field '{field}' must be a JSON object.")

    return cast(JsonObject, value)


def _require_list(value: object, *, field: str) -> list[object]:
    """Einen Wert als JSON-Liste validieren und typisiert zurückgeben."""
    if not isinstance(value, list):
        raise ValueError(f"Field '{field}' must be a JSON list.")

    return cast(list[object], value)


def _require_string(value: object, *, field: str) -> str:
    """Einen nicht leeren String validieren."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty string.")

    return value


def _require_positive_int(value: object, *, field: str) -> int:
    """Eine positive Ganzzahl validieren und dabei ``bool`` ausschließen."""
    # Wie schon im Collector gilt: ``bool`` ist in Python eine Unterklasse von
    # ``int``. Deshalb muss True/False ausdrücklich ausgeschlossen werden.
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"Field '{field}' must be a positive integer.")

    return value


def _require_non_negative_int(value: object, *, field: str) -> int:
    """Eine Ganzzahl größer oder gleich null validieren."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Field '{field}' must be a non-negative integer.")

    return value


def _extract_types(payload: JsonObject) -> tuple[str, str | None]:
    """Primären und optionalen sekundären Typ anhand des API-Slots extrahieren."""
    raw_types = _require_list(payload.get("types"), field="types")
    types_by_slot: dict[int, str] = {}

    for index, raw_entry in enumerate(raw_types):
        entry = _require_object(raw_entry, field=f"types[{index}]")
        slot = _require_positive_int(entry.get("slot"), field=f"types[{index}].slot")

        # Unser MVP kennt pro Pokémon höchstens zwei aktive Typen. Ein anderer Slot
        # wäre ein unerwarteter Schemawechsel und soll nicht still ignoriert werden.
        if slot not in (1, 2):
            raise ValueError("Pokémon type slot must be 1 or 2.")
        if slot in types_by_slot:
            raise ValueError(f"Duplicate Pokémon type slot: {slot}.")

        type_object = _require_object(entry.get("type"), field=f"types[{index}].type")
        type_name = _require_string(
            type_object.get("name"),
            field=f"types[{index}].type.name",
        )
        types_by_slot[slot] = type_name

    # Ein Pokémon ohne primären Typ wäre für alle späteren Typenberechnungen
    # unbrauchbar. Deshalb behandeln wir das als Datenfehler.
    if 1 not in types_by_slot:
        raise ValueError("Pokémon must have a type in slot 1.")

    return types_by_slot[1], types_by_slot.get(2)


def _extract_stats(payload: JsonObject) -> dict[str, int]:
    """Die sechs benötigten Basiswerte anhand ihrer Namen extrahieren."""
    raw_stats = _require_list(payload.get("stats"), field="stats")
    stats: dict[str, int] = {}

    for index, raw_entry in enumerate(raw_stats):
        entry = _require_object(raw_entry, field=f"stats[{index}]")
        stat_object = _require_object(entry.get("stat"), field=f"stats[{index}].stat")
        stat_name = _require_string(
            stat_object.get("name"),
            field=f"stats[{index}].stat.name",
        )

        # Zusätzliche Stats würden nicht automatisch Teil unseres fest definierten
        # MVP-Schemas. Wir ignorieren sie, verlangen aber weiterhin alle sechs
        # erwarteten Stats weiter unten.
        if stat_name not in EXPECTED_STAT_NAMES:
            continue
        if stat_name in stats:
            raise ValueError(f"Duplicate Pokémon stat: {stat_name}.")

        stats[stat_name] = _require_non_negative_int(
            entry.get("base_stat"),
            field=f"stats[{index}].base_stat",
        )

    missing_stats = EXPECTED_STAT_NAMES.difference(stats)
    if missing_stats:
        missing = ", ".join(sorted(missing_stats))
        raise ValueError(f"Missing Pokémon stats: {missing}.")

    return stats


def _extract_sprite_url(payload: JsonObject) -> str | None:
    """Die Standard-Frontansicht extrahieren; fehlende Sprites bleiben ``None``."""
    sprites = _require_object(payload.get("sprites"), field="sprites")
    sprite_url = sprites.get("front_default")

    # Ein fehlendes Bild ist kein Grund, einen fachlich gültigen Datensatz zu
    # verwerfen. Die Streamlit-Oberfläche kann später einen Platzhalter anzeigen.
    if sprite_url is None:
        return None

    return _require_string(sprite_url, field="sprites.front_default")


def prepare_pokemon(payload: JsonObject) -> PokemonRecord | None:
    """Eine rohe PokéAPI-Antwort in einen MVP-Datensatz transformieren.

    Nicht-Standardformen werden durch ``None`` signalisiert. Das ist kein Fehler,
    sondern die bewusst festgelegte Projektgrenze unseres MVP.
    """
    is_default = payload.get("is_default")
    if not isinstance(is_default, bool):
        raise ValueError("Field 'is_default' must be a boolean.")

    # Früh filtern: Daten einer Form, die wir bewusst nicht verwenden, müssen nicht
    # unnötig vollständig validiert und transformiert werden.
    if not is_default:
        return None

    pokemon_id = _require_positive_int(payload.get("id"), field="id")
    name = _require_string(payload.get("name"), field="name")
    type_1, type_2 = _extract_types(payload)
    stats = _extract_stats(payload)
    sprite_url = _extract_sprite_url(payload)

    # Der Base Stat Total ist ein Feature Engineering-Schritt: Er existiert nicht
    # als eigenes Feld in unserer Rohantwort, sondern ist die Summe der sechs
    # Basiswerte. Die einzelnen Stats bleiben trotzdem erhalten.
    base_stat_total = sum(stats[name] for name in EXPECTED_STAT_NAMES)

    return PokemonRecord(
        id=pokemon_id,
        name=name,
        is_default=is_default,
        type_1=type_1,
        type_2=type_2,
        hp=stats["hp"],
        attack=stats["attack"],
        defense=stats["defense"],
        special_attack=stats["special-attack"],
        special_defense=stats["special-defense"],
        speed=stats["speed"],
        base_stat_total=base_stat_total,
        sprite_url=sprite_url,
    )


def load_raw_pokemon(path: Path) -> JsonObject:
    """Eine rohe JSON-Datei laden und ihre oberste Struktur validieren."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return _require_object(payload, field=str(path))


def prepare_raw_directory(raw_directory: Path) -> list[PokemonRecord]:
    """Alle Rohdateien eines Verzeichnisses aufbereiten und nach ID sortieren."""
    if not raw_directory.is_dir():
        raise FileNotFoundError(f"Raw data directory does not exist: {raw_directory}")

    records: list[PokemonRecord] = []
    seen_ids: set[int] = set()

    # Die Dateinamen werden zuerst sortiert. Die endgültige Sortierung nach ID
    # weiter unten macht die Ausgabe anschließend unabhängig vom Dateinamen.
    for path in sorted(raw_directory.glob("*.json")):
        record = prepare_pokemon(load_raw_pokemon(path))
        if record is None:
            continue

        pokemon_id = record["id"]
        if pokemon_id in seen_ids:
            raise ValueError(f"Duplicate prepared Pokémon ID: {pokemon_id}.")

        seen_ids.add(pokemon_id)
        records.append(record)

    records.sort(key=lambda record: record["id"])
    return records


def write_processed_csv(
    records: Iterable[PokemonRecord],
    *,
    output_path: Path,
) -> Path:
    """Aufbereitete Datensätze deterministisch und atomar als CSV schreiben."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    # ``newline=''`` ist die von ``csv`` empfohlene Öffnungsart. Ein expliziter
    # ``lineterminator`` hält die Ausgabe zusätzlich zwischen Windows und Linux
    # reproduzierbar.
    with temporary_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=PROCESSED_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(records)

    # Wie beim Rohdaten-Cache wird erst die vollständig geschriebene Datei zum
    # endgültigen Ergebnis. So bleibt bei einem Abbruch keine halbe CSV zurück.
    temporary_path.replace(output_path)
    return output_path


def prepare_dataset(
    *,
    raw_directory: Path,
    output_path: Path,
) -> list[PokemonRecord]:
    """Rohdaten aufbereiten, als CSV speichern und die Datensätze zurückgeben."""
    records = prepare_raw_directory(raw_directory)
    write_processed_csv(records, output_path=output_path)
    return records
