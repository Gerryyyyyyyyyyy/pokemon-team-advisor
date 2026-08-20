"""Unit Tests für den sicheren PostgreSQL-Import."""

import csv
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from pokemon_team_advisor.database import DatabaseConnection
from pokemon_team_advisor.database_loader import (
    POKEMON_COLUMNS,
    UPSERT_POKEMON_SQL,
    PokemonDatabaseRow,
    read_pokemon_csv,
    upsert_pokemon_rows,
)


def _pokemon_values() -> dict[str, object]:
    """Eine vollständige vorbereitete Bulbasaur-Zeile erzeugen."""
    return {
        "id": 1,
        "name": "bulbasaur",
        "species_name": "bulbasaur",
        "is_default": True,
        "type_1": "grass",
        "type_2": "poison",
        "hp": 45,
        "attack": 49,
        "defense": 49,
        "special_attack": 65,
        "special_defense": 65,
        "speed": 45,
        "base_stat_total": 318,
        "sprite_url": (
            "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png"
        ),
        "generation": 1,
        "evolution_chain_id": 1,
        "evolution_family": "bulbasaur",
        "evolution_stage": 0,
        "evolution_max_stage": 2,
        "is_final_evolution": False,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Testdaten mit derselben Spaltenreihenfolge wie der echte Export schreiben."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=POKEMON_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _database_row() -> PokemonDatabaseRow:
    """Eine bereits typisierte Datenbankzeile für Schreibtests erzeugen."""
    path_values = _pokemon_values()
    return (
        1,
        "bulbasaur",
        "bulbasaur",
        True,
        "grass",
        "poison",
        45,
        49,
        49,
        65,
        65,
        45,
        318,
        str(path_values["sprite_url"]),
        1,
        1,
        "bulbasaur",
        0,
        2,
        False,
    )


def test_read_pokemon_csv_converts_database_types(tmp_path: Path) -> None:
    """CSV-Texte werden vor dem Import in Python-Typen umgewandelt."""
    path = tmp_path / "pokemon.csv"
    row = _pokemon_values()
    row["type_2"] = ""
    _write_csv(path, [row])

    result = read_pokemon_csv(path)

    assert len(result) == 1
    assert result[0][0] == 1
    assert result[0][3] is True
    assert result[0][5] is None
    assert result[0][19] is False


def test_read_pokemon_csv_accepts_different_column_order(tmp_path: Path) -> None:
    """Die Zuordnung erfolgt über Namen und hängt nicht von der CSV-Reihenfolge ab."""
    path = tmp_path / "pokemon.csv"
    reordered_columns = tuple(column for column in POKEMON_COLUMNS if column != "sprite_url") + (
        "sprite_url",
    )

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=reordered_columns,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(_pokemon_values())

    result = read_pokemon_csv(path)

    assert result[0][0] == 1
    assert result[0][13].endswith("/1.png")


def test_read_pokemon_csv_rejects_wrong_columns(tmp_path: Path) -> None:
    """Eine veraltete oder fremde CSV nicht still in die Tabelle laden."""
    path = tmp_path / "pokemon.csv"
    path.write_text("id,name\n1,bulbasaur\n", encoding="utf-8")

    with pytest.raises(ValueError, match="columns do not match"):
        read_pokemon_csv(path)


def test_read_pokemon_csv_rejects_duplicate_ids(tmp_path: Path) -> None:
    """Doppelte IDs bereits vor Beginn der Datenbanktransaktion erkennen."""
    path = tmp_path / "pokemon.csv"
    first = _pokemon_values()
    second = {**first, "name": "duplicate-name"}
    _write_csv(path, [first, second])

    with pytest.raises(ValueError, match="Duplicate Pokémon ID"):
        read_pokemon_csv(path)


def test_upsert_uses_parameters_and_commits() -> None:
    """Werte gebunden übertragen und eine erfolgreiche Transaktion bestätigen."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    row = _database_row()

    result = upsert_pokemon_rows(
        cast(DatabaseConnection, connection),
        [row],
    )

    assert result == 1
    cursor.executemany.assert_called_once_with(UPSERT_POKEMON_SQL, [row])
    assert UPSERT_POKEMON_SQL.count("%s") == len(POKEMON_COLUMNS)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()


def test_upsert_rolls_back_complete_import_on_failure() -> None:
    """Nach einem Schreibfehler keine teilweise importierten Zeilen behalten."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.executemany.side_effect = RuntimeError("database rejected row")

    with pytest.raises(RuntimeError, match="database rejected row"):
        upsert_pokemon_rows(
            cast(DatabaseConnection, connection),
            [_database_row()],
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
