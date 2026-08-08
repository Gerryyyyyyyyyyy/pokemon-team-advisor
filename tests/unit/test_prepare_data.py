"""Unit Tests für die Transformation von PokéAPI-Rohdaten."""

import csv
import json
from pathlib import Path

import pytest

from pokemon_team_advisor.prepare_data import (
    prepare_dataset,
    prepare_pokemon,
    prepare_raw_directory,
)


def _pokemon_payload(
    *,
    pokemon_id: int = 1,
    name: str = "bulbasaur",
    is_default: bool = True,
) -> dict[str, object]:
    """Kleinen realistischen PokéAPI-Payload für mehrere Tests erzeugen."""
    return {
        "id": pokemon_id,
        "name": name,
        "is_default": is_default,
        # Die Typen stehen absichtlich in umgekehrter Listenreihenfolge. Damit
        # beweist der Test später, dass unsere Logik den API-Slot verwendet.
        "types": [
            {"slot": 2, "type": {"name": "poison"}},
            {"slot": 1, "type": {"name": "grass"}},
        ],
        # Auch die Stats sind bewusst gemischt. Ihre Bedeutung kommt aus
        # ``stat.name`` und niemals aus ihrer Position in der Liste.
        "stats": [
            {"base_stat": 45, "stat": {"name": "speed"}},
            {"base_stat": 65, "stat": {"name": "special-defense"}},
            {"base_stat": 49, "stat": {"name": "attack"}},
            {"base_stat": 45, "stat": {"name": "hp"}},
            {"base_stat": 65, "stat": {"name": "special-attack"}},
            {"base_stat": 49, "stat": {"name": "defense"}},
        ],
        "sprites": {
            "front_default": "https://example.test/sprites/1.png",
        },
    }


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    """Test-Payload als UTF-8-JSON ablegen."""
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prepare_pokemon_extracts_mvp_fields_by_name_and_slot() -> None:
    record = prepare_pokemon(_pokemon_payload())

    assert record == {
        "id": 1,
        "name": "bulbasaur",
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
        "sprite_url": "https://example.test/sprites/1.png",
    }


def test_prepare_pokemon_supports_single_type_and_missing_sprite() -> None:
    payload = _pokemon_payload(pokemon_id=4, name="charmander")
    payload["types"] = [{"slot": 1, "type": {"name": "fire"}}]
    payload["sprites"] = {"front_default": None}

    record = prepare_pokemon(payload)

    assert record is not None
    assert record["type_1"] == "fire"
    assert record["type_2"] is None
    assert record["sprite_url"] is None


def test_prepare_pokemon_filters_non_default_form() -> None:
    # Nicht-Standardformen gehören laut MVP bewusst nicht in die fertige Tabelle.
    assert prepare_pokemon(_pokemon_payload(is_default=False)) is None


def test_prepare_pokemon_rejects_missing_required_stat() -> None:
    payload = _pokemon_payload()
    stats = payload["stats"]
    assert isinstance(stats, list)
    stats.pop()

    with pytest.raises(ValueError, match="Missing Pokémon stats: defense"):
        prepare_pokemon(payload)


def test_prepare_pokemon_rejects_duplicate_stat() -> None:
    payload = _pokemon_payload()
    stats = payload["stats"]
    assert isinstance(stats, list)
    stats.append({"base_stat": 99, "stat": {"name": "hp"}})

    with pytest.raises(ValueError, match="Duplicate Pokémon stat: hp"):
        prepare_pokemon(payload)


def test_prepare_pokemon_rejects_duplicate_type_slot() -> None:
    payload = _pokemon_payload()
    payload["types"] = [
        {"slot": 1, "type": {"name": "grass"}},
        {"slot": 1, "type": {"name": "poison"}},
    ]

    with pytest.raises(ValueError, match="Duplicate Pokémon type slot: 1"):
        prepare_pokemon(payload)


def test_prepare_raw_directory_filters_and_sorts_records(tmp_path: Path) -> None:
    # Dateinamen und IDs sind bewusst nicht gleich sortiert. Zusätzlich liegt eine
    # Nicht-Standardform dazwischen, die im Ergebnis verschwinden soll.
    _write_payload(
        tmp_path / "a.json",
        _pokemon_payload(pokemon_id=4, name="charmander"),
    )
    _write_payload(
        tmp_path / "b.json",
        _pokemon_payload(pokemon_id=10001, name="test-form", is_default=False),
    )
    _write_payload(
        tmp_path / "z.json",
        _pokemon_payload(pokemon_id=1, name="bulbasaur"),
    )

    records = prepare_raw_directory(tmp_path)

    assert [record["id"] for record in records] == [1, 4]
    assert [record["name"] for record in records] == ["bulbasaur", "charmander"]


def test_prepare_raw_directory_rejects_duplicate_ids(tmp_path: Path) -> None:
    _write_payload(tmp_path / "first.json", _pokemon_payload())
    _write_payload(tmp_path / "second.json", _pokemon_payload())

    with pytest.raises(ValueError, match="Duplicate prepared Pokémon ID: 1"):
        prepare_raw_directory(tmp_path)


def test_prepare_raw_directory_requires_existing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Raw data directory does not exist"):
        prepare_raw_directory(tmp_path / "missing")


def test_prepare_dataset_writes_deterministic_csv(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    _write_payload(raw_directory / "0001.json", _pokemon_payload())
    output_path = tmp_path / "processed" / "pokemon.csv"

    records = prepare_dataset(
        raw_directory=raw_directory,
        output_path=output_path,
    )

    with output_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(records) == 1
    assert rows[0]["name"] == "bulbasaur"
    assert rows[0]["type_1"] == "grass"
    assert rows[0]["type_2"] == "poison"
    assert rows[0]["base_stat_total"] == "318"
    assert output_path.read_bytes().endswith(b"\n")
    assert not output_path.with_suffix(".csv.tmp").exists()
