"""Unit Tests für die Berechnung der Typeneffektivität."""

import csv
import json
from pathlib import Path

import pytest

from pokemon_team_advisor.type_effectiveness import (
    build_type_chart,
    calculate_type_multiplier,
    load_type_payloads,
    prepare_type_dataset,
    prepare_type_directory,
    prepare_type_row,
    write_type_chart_csv,
)

TEST_CHART: dict[str, dict[str, float]] = {
    "fire": {
        "grass": 2.0,
        "steel": 2.0,
        "water": 0.5,
        "dragon": 0.5,
        "normal": 1.0,
    },
    "ground": {
        "electric": 2.0,
        "flying": 0.0,
    },
}


def _type_payload(
    name: str,
    *,
    double_to: tuple[str, ...] = (),
    half_to: tuple[str, ...] = (),
    no_damage_to: tuple[str, ...] = (),
) -> dict[str, object]:
    """Kleine PokéAPI-Type-Antwort für Matrixtests erzeugen."""

    def resources(type_names: tuple[str, ...]) -> list[dict[str, str]]:
        return [{"name": type_name} for type_name in type_names]

    return {
        "name": name,
        "damage_relations": {
            "double_damage_to": resources(double_to),
            "half_damage_to": resources(half_to),
            "no_damage_to": resources(no_damage_to),
        },
    }


def _write_type_payload(
    path: Path,
    payload: dict[str, object],
) -> None:
    """Eine kleine Type-Antwort als UTF-8-JSON ablegen."""
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    ("defending_types", "expected"),
    [
        (("grass",), 2.0),
        (("grass", "steel"), 4.0),
        (("water", "dragon"), 0.25),
        (("normal",), 1.0),
    ],
)
def test_calculate_type_multiplier_multiplies_defending_types(
    defending_types: tuple[str, ...],
    expected: float,
) -> None:
    result = calculate_type_multiplier(
        "fire",
        defending_types,
        chart=TEST_CHART,
    )

    assert result == expected


def test_calculate_type_multiplier_immunity_dominates_weakness() -> None:
    result = calculate_type_multiplier(
        "ground",
        ("electric", "flying"),
        chart=TEST_CHART,
    )

    assert result == 0.0


def test_prepare_type_row_builds_complete_offensive_row() -> None:
    """Explizite API-Beziehungen und neutrale Kombinationen verbinden."""
    payload: dict[str, object] = {
        "name": "fire",
        "damage_relations": {
            "double_damage_to": [
                {"name": "grass"},
                {"name": "steel"},
            ],
            "half_damage_to": [
                {"name": "fire"},
                {"name": "water"},
                {"name": "dragon"},
            ],
            "no_damage_to": [],
        },
    }
    supported_types = frozenset(
        {
            "fire",
            "grass",
            "steel",
            "water",
            "dragon",
            "normal",
        }
    )

    attacking_type, row = prepare_type_row(
        payload,
        supported_types=supported_types,
    )

    assert attacking_type == "fire"
    assert row == {
        "dragon": 0.5,
        "fire": 0.5,
        "grass": 2.0,
        "normal": 1.0,
        "steel": 2.0,
        "water": 0.5,
    }


def test_prepare_type_row_supports_immunity() -> None:
    """Eine Immunität aus no_damage_to als Multiplikator null abbilden."""
    payload: dict[str, object] = {
        "name": "ground",
        "damage_relations": {
            "double_damage_to": [{"name": "electric"}],
            "half_damage_to": [],
            "no_damage_to": [{"name": "flying"}],
        },
    }

    attacking_type, row = prepare_type_row(
        payload,
        supported_types=frozenset({"ground", "electric", "flying"}),
    )

    assert attacking_type == "ground"
    assert row["electric"] == 2.0
    assert row["flying"] == 0.0
    assert row["ground"] == 1.0


def test_prepare_type_row_rejects_conflicting_relations() -> None:
    """Denselben Verteidigertyp nicht mehreren Kategorien zuordnen."""
    payload: dict[str, object] = {
        "name": "fire",
        "damage_relations": {
            "double_damage_to": [{"name": "grass"}],
            "half_damage_to": [{"name": "grass"}],
            "no_damage_to": [],
        },
    }

    with pytest.raises(ValueError, match="multiple damage relations"):
        prepare_type_row(
            payload,
            supported_types=frozenset({"fire", "grass"}),
        )


def test_build_type_chart_combines_all_type_rows() -> None:
    """Alle unterstützten Angriffstypen zu einer quadratischen Matrix verbinden."""
    payloads = [
        _type_payload("fire", double_to=("grass",), half_to=("water",)),
        _type_payload("grass", double_to=("water",), half_to=("fire",)),
        _type_payload("water", double_to=("fire",), half_to=("grass",)),
    ]

    chart = build_type_chart(
        payloads,
        supported_types=frozenset({"fire", "grass", "water"}),
    )

    assert chart == {
        "fire": {
            "fire": 1.0,
            "grass": 2.0,
            "water": 0.5,
        },
        "grass": {
            "fire": 0.5,
            "grass": 1.0,
            "water": 2.0,
        },
        "water": {
            "fire": 2.0,
            "grass": 0.5,
            "water": 1.0,
        },
    }


def test_build_type_chart_rejects_missing_attack_type() -> None:
    """Eine unvollständige Matrix nicht unbemerkt akzeptieren."""
    payloads = [
        _type_payload("fire"),
        _type_payload("grass"),
    ]

    with pytest.raises(ValueError, match="Missing attacking types: water"):
        build_type_chart(
            payloads,
            supported_types=frozenset({"fire", "grass", "water"}),
        )


def test_build_type_chart_rejects_duplicate_attack_type() -> None:
    """Für jeden Angriffstyp genau eine API-Antwort verlangen."""
    payloads = [
        _type_payload("fire"),
        _type_payload("fire"),
    ]

    with pytest.raises(ValueError, match="Duplicate attacking type: fire"):
        build_type_chart(
            payloads,
            supported_types=frozenset({"fire"}),
        )


def test_load_type_payloads_sorts_files(tmp_path: Path) -> None:
    """Die Verarbeitung unabhängig von der Erstellungsreihenfolge halten."""
    _write_type_payload(tmp_path / "water.json", _type_payload("water"))
    _write_type_payload(tmp_path / "fire.json", _type_payload("fire"))

    payloads = load_type_payloads(tmp_path)

    assert [payload["name"] for payload in payloads] == ["fire", "water"]


def test_load_type_payloads_requires_existing_directory(tmp_path: Path) -> None:
    """Ein fehlendes Raw-Verzeichnis mit einer klaren Meldung ablehnen."""
    with pytest.raises(FileNotFoundError, match="Raw type directory does not exist"):
        load_type_payloads(tmp_path / "missing")


def test_load_type_payloads_rejects_mismatched_filename(tmp_path: Path) -> None:
    """Eine falsch benannte Cache-Datei nicht still weiterverarbeiten."""
    _write_type_payload(tmp_path / "fire.json", _type_payload("water"))

    with pytest.raises(ValueError, match="filename does not match payload name"):
        load_type_payloads(tmp_path)


def test_write_type_chart_csv_rejects_non_square_chart(tmp_path: Path) -> None:
    """Jede Zeile muss dieselben Verteidigertypen wie die Matrix besitzen."""
    incomplete_chart = {
        "fire": {"fire": 1.0, "water": 0.5},
        "water": {"water": 1.0},
    }

    with pytest.raises(ValueError, match="is not square"):
        write_type_chart_csv(
            incomplete_chart,
            output_path=tmp_path / "type_effectiveness.csv",
        )


def test_prepare_type_dataset_writes_deterministic_matrix_csv(
    tmp_path: Path,
) -> None:
    """Raw-Dateien vollständig in eine lesbare Angriff-mal-Verteidigung-CSV führen."""
    raw_directory = tmp_path / "raw" / "types"
    raw_directory.mkdir(parents=True)

    _write_type_payload(
        raw_directory / "fire.json",
        _type_payload("fire", double_to=("grass",), half_to=("water",)),
    )
    _write_type_payload(
        raw_directory / "grass.json",
        _type_payload("grass", double_to=("water",), half_to=("fire",)),
    )
    _write_type_payload(
        raw_directory / "water.json",
        _type_payload("water", double_to=("fire",), half_to=("grass",)),
    )

    output_path = tmp_path / "processed" / "type_effectiveness.csv"
    supported_types = frozenset({"fire", "grass", "water"})

    chart = prepare_type_dataset(
        raw_directory=raw_directory,
        supported_types=supported_types,
        output_path=output_path,
    )

    with output_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert (
        prepare_type_directory(
            raw_directory,
            supported_types=supported_types,
        )
        == chart
    )
    assert list(chart) == ["fire", "grass", "water"]
    assert rows == [
        {
            "attacking_type": "fire",
            "fire": "1.0",
            "grass": "2.0",
            "water": "0.5",
        },
        {
            "attacking_type": "grass",
            "fire": "0.5",
            "grass": "1.0",
            "water": "2.0",
        },
        {
            "attacking_type": "water",
            "fire": "2.0",
            "grass": "0.5",
            "water": "1.0",
        },
    ]
    assert output_path.read_bytes().endswith(b"\n")
    assert not output_path.with_suffix(".csv.tmp").exists()
