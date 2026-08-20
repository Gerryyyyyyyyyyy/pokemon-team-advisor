"""Aufbereitete Pokémon-Daten sicher und reproduzierbar nach PostgreSQL laden."""

import csv
from pathlib import Path

from pokemon_team_advisor.database import DatabaseConnection, connect_database

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POKEMON_CSV = PROJECT_ROOT / "data" / "processed" / "pokemon.csv"

# Diese Namen definieren das erwartete CSV-Schema und die Reihenfolge der Werte
# für die INSERT-Anweisung. Die CSV selbst darf ihre Spalten anders anordnen,
# weil ``DictReader`` jede Zelle über den Spaltennamen zuordnet. ``loaded_at``
# wird von PostgreSQL gesetzt und steht deshalb nicht in dieser Liste.
POKEMON_COLUMNS = (
    "id",
    "name",
    "species_name",
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
    "generation",
    "evolution_chain_id",
    "evolution_family",
    "evolution_stage",
    "evolution_max_stage",
    "is_final_evolution",
)

type PokemonDatabaseRow = tuple[
    int,
    str,
    str,
    bool,
    str,
    str | None,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    str,
    int,
    int,
    str,
    int,
    int,
    bool,
]

# Tabellen- und Spaltennamen sind fest im Quellcode definiert. Ausschließlich die
# Werte werden über psycopg-Platzhalter übertragen. CSV-Inhalte können dadurch
# nicht als SQL interpretiert werden.
UPSERT_POKEMON_SQL = """
INSERT INTO analytics.pokemon (
    id,
    name,
    species_name,
    is_default,
    type_1,
    type_2,
    hp,
    attack,
    defense,
    special_attack,
    special_defense,
    speed,
    base_stat_total,
    sprite_url,
    generation,
    evolution_chain_id,
    evolution_family,
    evolution_stage,
    evolution_max_stage,
    is_final_evolution
)
VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    species_name = EXCLUDED.species_name,
    is_default = EXCLUDED.is_default,
    type_1 = EXCLUDED.type_1,
    type_2 = EXCLUDED.type_2,
    hp = EXCLUDED.hp,
    attack = EXCLUDED.attack,
    defense = EXCLUDED.defense,
    special_attack = EXCLUDED.special_attack,
    special_defense = EXCLUDED.special_defense,
    speed = EXCLUDED.speed,
    base_stat_total = EXCLUDED.base_stat_total,
    sprite_url = EXCLUDED.sprite_url,
    generation = EXCLUDED.generation,
    evolution_chain_id = EXCLUDED.evolution_chain_id,
    evolution_family = EXCLUDED.evolution_family,
    evolution_stage = EXCLUDED.evolution_stage,
    evolution_max_stage = EXCLUDED.evolution_max_stage,
    is_final_evolution = EXCLUDED.is_final_evolution,
    loaded_at = CURRENT_TIMESTAMP
WHERE (
    analytics.pokemon.name,
    analytics.pokemon.species_name,
    analytics.pokemon.is_default,
    analytics.pokemon.type_1,
    analytics.pokemon.type_2,
    analytics.pokemon.hp,
    analytics.pokemon.attack,
    analytics.pokemon.defense,
    analytics.pokemon.special_attack,
    analytics.pokemon.special_defense,
    analytics.pokemon.speed,
    analytics.pokemon.base_stat_total,
    analytics.pokemon.sprite_url,
    analytics.pokemon.generation,
    analytics.pokemon.evolution_chain_id,
    analytics.pokemon.evolution_family,
    analytics.pokemon.evolution_stage,
    analytics.pokemon.evolution_max_stage,
    analytics.pokemon.is_final_evolution
) IS DISTINCT FROM (
    EXCLUDED.name,
    EXCLUDED.species_name,
    EXCLUDED.is_default,
    EXCLUDED.type_1,
    EXCLUDED.type_2,
    EXCLUDED.hp,
    EXCLUDED.attack,
    EXCLUDED.defense,
    EXCLUDED.special_attack,
    EXCLUDED.special_defense,
    EXCLUDED.speed,
    EXCLUDED.base_stat_total,
    EXCLUDED.sprite_url,
    EXCLUDED.generation,
    EXCLUDED.evolution_chain_id,
    EXCLUDED.evolution_family,
    EXCLUDED.evolution_stage,
    EXCLUDED.evolution_max_stage,
    EXCLUDED.is_final_evolution
)
"""


def _required_text(value: str | None, *, field: str, row_number: int) -> str:
    """Ein Pflichttextfeld aus der CSV lesen und Leerwerte ablehnen."""
    text = value.strip() if value is not None else ""
    if not text:
        raise ValueError(f"CSV row {row_number}: field '{field}' must not be empty.")
    return text


def _integer(value: str | None, *, field: str, row_number: int) -> int:
    """Eine dezimale Ganzzahl lesen, ohne still Nachkommastellen abzuschneiden."""
    text = _required_text(value, field=field, row_number=row_number)
    if not text.isdigit():
        raise ValueError(f"CSV row {row_number}: field '{field}' must be an integer.")
    return int(text)


def _boolean(value: str | None, *, field: str, row_number: int) -> bool:
    """Nur die eindeutigen CSV-Werte True und False akzeptieren."""
    text = _required_text(value, field=field, row_number=row_number)
    if text == "True":
        return True
    if text == "False":
        return False
    raise ValueError(f"CSV row {row_number}: field '{field}' must be True or False.")


def _prepare_database_row(
    raw: dict[str, str | None],
    *,
    row_number: int,
) -> PokemonDatabaseRow:
    """Eine CSV-Zeile typisieren, bevor psycopg sie an PostgreSQL überträgt."""
    raw_type_2 = raw.get("type_2")
    type_2 = raw_type_2.strip() if raw_type_2 is not None else ""

    return (
        _integer(raw.get("id"), field="id", row_number=row_number),
        _required_text(raw.get("name"), field="name", row_number=row_number),
        _required_text(raw.get("species_name"), field="species_name", row_number=row_number),
        _boolean(raw.get("is_default"), field="is_default", row_number=row_number),
        _required_text(raw.get("type_1"), field="type_1", row_number=row_number),
        type_2 or None,
        _integer(raw.get("hp"), field="hp", row_number=row_number),
        _integer(raw.get("attack"), field="attack", row_number=row_number),
        _integer(raw.get("defense"), field="defense", row_number=row_number),
        _integer(raw.get("special_attack"), field="special_attack", row_number=row_number),
        _integer(raw.get("special_defense"), field="special_defense", row_number=row_number),
        _integer(raw.get("speed"), field="speed", row_number=row_number),
        _integer(raw.get("base_stat_total"), field="base_stat_total", row_number=row_number),
        _required_text(raw.get("sprite_url"), field="sprite_url", row_number=row_number),
        _integer(raw.get("generation"), field="generation", row_number=row_number),
        _integer(
            raw.get("evolution_chain_id"),
            field="evolution_chain_id",
            row_number=row_number,
        ),
        _required_text(
            raw.get("evolution_family"),
            field="evolution_family",
            row_number=row_number,
        ),
        _integer(
            raw.get("evolution_stage"),
            field="evolution_stage",
            row_number=row_number,
        ),
        _integer(
            raw.get("evolution_max_stage"),
            field="evolution_max_stage",
            row_number=row_number,
        ),
        _boolean(
            raw.get("is_final_evolution"),
            field="is_final_evolution",
            row_number=row_number,
        ),
    )


def read_pokemon_csv(path: Path) -> list[PokemonDatabaseRow]:
    """Die aufbereitete CSV vollständig validieren und typisiert einlesen."""
    if not path.is_file():
        raise FileNotFoundError(f"Processed Pokémon CSV does not exist: {path}")

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        actual_columns = tuple(reader.fieldnames or ())
        expected_column_set = set(POKEMON_COLUMNS)
        actual_column_set = set(actual_columns)

        # Eine abweichende Reihenfolge ist ungefährlich. Doppelte, fehlende oder
        # zusätzliche Namen würden dagegen eine Zelle uneindeutig zuordnen oder
        # ein anderes Schema vortäuschen.
        has_duplicate_columns = len(actual_columns) != len(actual_column_set)
        missing_columns = expected_column_set.difference(actual_column_set)
        unexpected_columns = actual_column_set.difference(expected_column_set)
        if has_duplicate_columns or missing_columns or unexpected_columns:
            missing = ", ".join(sorted(missing_columns)) or "none"
            unexpected = ", ".join(sorted(unexpected_columns)) or "none"
            raise ValueError(
                "Processed Pokémon CSV columns do not match the database schema; "
                f"missing=[{missing}], unexpected=[{unexpected}]."
            )

        rows: list[PokemonDatabaseRow] = []
        seen_ids: set[int] = set()
        seen_names: set[str] = set()

        # Zeile 1 enthält den Header; der erste Datensatz steht deshalb in Zeile 2.
        for row_number, raw in enumerate(reader, start=2):
            row = _prepare_database_row(raw, row_number=row_number)
            pokemon_id, name = row[0], row[1]

            if pokemon_id in seen_ids:
                raise ValueError(f"Duplicate Pokémon ID in CSV: {pokemon_id}.")
            if name in seen_names:
                raise ValueError(f"Duplicate Pokémon name in CSV: {name}.")

            seen_ids.add(pokemon_id)
            seen_names.add(name)
            rows.append(row)

    if not rows:
        raise ValueError("Processed Pokémon CSV must contain at least one row.")

    return rows


def upsert_pokemon_rows(
    connection: DatabaseConnection,
    rows: list[PokemonDatabaseRow],
) -> int:
    """Pokémon atomar und mit gebundenen Parametern in PostgreSQL schreiben."""
    if not rows:
        raise ValueError("At least one Pokémon row is required for the database import.")

    try:
        with connection.cursor() as cursor:
            cursor.executemany(UPSERT_POKEMON_SQL, rows)
        connection.commit()
    except Exception:
        # Bei einem einzigen ungültigen Datensatz wird der komplette Import
        # zurückgerollt. Die Tabelle bleibt dadurch in einem konsistenten Zustand.
        connection.rollback()
        raise

    return len(rows)


def import_pokemon_csv(path: Path = DEFAULT_POKEMON_CSV) -> int:
    """CSV lesen, Verbindung öffnen und alle Zeilen kontrolliert importieren."""
    rows = read_pokemon_csv(path)
    connection = connect_database()

    try:
        return upsert_pokemon_rows(connection, rows)
    finally:
        connection.close()


def main() -> None:
    """Den lokalen Processed-Datensatz über ``python -m`` importieren."""
    imported_count = import_pokemon_csv()
    print(f"{imported_count} Pokémon nach PostgreSQL übertragen.")


if __name__ == "__main__":
    main()
