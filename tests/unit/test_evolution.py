"""Unit Tests für die Ableitung von Evolutionsmerkmalen."""

import json
from pathlib import Path

import pytest

from pokemon_team_advisor.evolution import (
    build_evolution_features,
    load_species_evolution_data,
    parse_species_evolution_data,
    prepare_evolution_directory,
)


def _write_species_payload(
    path: Path,
    *,
    name: str,
    evolves_from: str | None,
    chain_id: int,
    generation: int,
) -> None:
    """Kleine realistische Species-Antwort für Verzeichnistests schreiben."""
    parent: dict[str, object] | None
    if evolves_from is None:
        parent = None
    else:
        parent = {
            "name": evolves_from,
            "url": f"https://pokeapi.co/api/v2/pokemon-species/{name}/",
        }

    payload: dict[str, object] = {
        "name": name,
        "evolves_from_species": parent,
        "evolution_chain": {
            "url": f"https://pokeapi.co/api/v2/evolution-chain/{chain_id}/",
        },
        "generation": {
            "url": f"https://pokeapi.co/api/v2/generation/{generation}/",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prepare_evolution_directory_loads_and_connects_species(
    tmp_path: Path,
) -> None:
    """Dateien unabhängig von ihrer Reihenfolge zu einer Kette verbinden."""
    _write_species_payload(
        tmp_path / "0026.json",
        name="raichu",
        evolves_from="pikachu",
        chain_id=10,
        generation=1,
    )
    _write_species_payload(
        tmp_path / "0172.json",
        name="pichu",
        evolves_from=None,
        chain_id=10,
        generation=2,
    )
    _write_species_payload(
        tmp_path / "0025.json",
        name="pikachu",
        evolves_from="pichu",
        chain_id=10,
        generation=1,
    )

    features = prepare_evolution_directory(tmp_path)

    assert features["pichu"]["evolution_stage"] == 0
    assert features["pikachu"]["evolution_stage"] == 1
    assert features["raichu"]["evolution_stage"] == 2
    assert features["raichu"]["is_final_evolution"] is True


def test_load_species_evolution_data_requires_existing_directory(
    tmp_path: Path,
) -> None:
    """Ein fehlendes Raw-Verzeichnis mit einer klaren Meldung ablehnen."""
    with pytest.raises(FileNotFoundError, match="Raw species directory does not exist"):
        load_species_evolution_data(tmp_path / "missing")


def test_load_species_evolution_data_rejects_non_object_json(
    tmp_path: Path,
) -> None:
    """Eine JSON-Liste nicht als Species-Antwort akzeptieren."""
    (tmp_path / "0001.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        load_species_evolution_data(tmp_path)


def test_parse_species_evolution_data_extracts_required_fields() -> None:
    """Relevante Felder aus einer realistischen Species-Antwort lesen."""
    payload: dict[str, object] = {
        "name": "ivysaur",
        "evolves_from_species": {
            "name": "bulbasaur",
            "url": "https://pokeapi.co/api/v2/pokemon-species/1/",
        },
        "evolution_chain": {
            "url": "https://pokeapi.co/api/v2/evolution-chain/1/",
        },
        "generation": {
            "name": "generation-i",
            "url": "https://pokeapi.co/api/v2/generation/1/",
        },
    }

    assert parse_species_evolution_data(payload) == {
        "name": "ivysaur",
        "evolves_from": "bulbasaur",
        "evolution_chain_id": 1,
        "generation": 1,
    }


def test_parse_species_evolution_data_supports_missing_parent() -> None:
    """Eine Spezies ohne Vorgänger als Wurzel der Kette einlesen."""
    payload: dict[str, object] = {
        "name": "bulbasaur",
        "evolves_from_species": None,
        "evolution_chain": {
            "url": "https://pokeapi.co/api/v2/evolution-chain/1/",
        },
        "generation": {
            "url": "https://pokeapi.co/api/v2/generation/1/",
        },
    }

    result = parse_species_evolution_data(payload)

    assert result["evolves_from"] is None
    assert result["evolution_chain_id"] == 1


def test_parse_species_evolution_data_rejects_wrong_resource_endpoint() -> None:
    """Eine Pokémon-URL nicht fälschlich als Evolutionskette akzeptieren."""
    payload: dict[str, object] = {
        "name": "bulbasaur",
        "evolves_from_species": None,
        "evolution_chain": {
            "url": "https://pokeapi.co/api/v2/pokemon/1/",
        },
        "generation": {
            "url": "https://pokeapi.co/api/v2/generation/1/",
        },
    }

    with pytest.raises(ValueError, match="unexpected resource URL"):
        parse_species_evolution_data(payload)


def test_build_evolution_features_supports_linear_and_standalone_chains() -> None:
    """Lineare Ketten und alleinstehende Pokémon korrekt unterscheiden."""
    features = build_evolution_features(
        [
            {
                "name": "pichu",
                "evolves_from": None,
                "evolution_chain_id": 10,
                "generation": 2,
            },
            {
                "name": "pikachu",
                "evolves_from": "pichu",
                "evolution_chain_id": 10,
                "generation": 1,
            },
            {
                "name": "raichu",
                "evolves_from": "pikachu",
                "evolution_chain_id": 10,
                "generation": 1,
            },
            {
                "name": "kangaskhan",
                "evolves_from": None,
                "evolution_chain_id": 20,
                "generation": 1,
            },
        ]
    )

    assert features == {
        "pichu": {
            "evolution_chain_id": 10,
            "evolution_family": "pichu",
            "evolution_stage": 0,
            "evolution_max_stage": 2,
            "is_final_evolution": False,
            "generation": 2,
        },
        "pikachu": {
            "evolution_chain_id": 10,
            "evolution_family": "pichu",
            "evolution_stage": 1,
            "evolution_max_stage": 2,
            "is_final_evolution": False,
            "generation": 1,
        },
        "raichu": {
            "evolution_chain_id": 10,
            "evolution_family": "pichu",
            "evolution_stage": 2,
            "evolution_max_stage": 2,
            "is_final_evolution": True,
            "generation": 1,
        },
        "kangaskhan": {
            "evolution_chain_id": 20,
            "evolution_family": "kangaskhan",
            "evolution_stage": 0,
            "evolution_max_stage": 0,
            "is_final_evolution": True,
            "generation": 1,
        },
    }


def test_build_evolution_features_supports_branching_chain() -> None:
    """Alle Enden einer Verzweigung als finale Entwicklungen markieren."""
    features = build_evolution_features(
        [
            {
                "name": "eevee",
                "evolves_from": None,
                "evolution_chain_id": 30,
                "generation": 1,
            },
            {
                "name": "vaporeon",
                "evolves_from": "eevee",
                "evolution_chain_id": 30,
                "generation": 1,
            },
            {
                "name": "sylveon",
                "evolves_from": "eevee",
                "evolution_chain_id": 30,
                "generation": 6,
            },
        ]
    )

    assert features["eevee"]["evolution_stage"] == 0
    assert features["eevee"]["evolution_family"] == "eevee"
    assert features["eevee"]["is_final_evolution"] is False
    assert features["vaporeon"]["evolution_stage"] == 1
    assert features["vaporeon"]["is_final_evolution"] is True
    assert features["sylveon"]["evolution_stage"] == 1
    assert features["sylveon"]["generation"] == 6


def test_build_evolution_features_normalizes_mismatched_chain_ids() -> None:
    """Verbundene Spezies trotz abweichender API-Ketten-IDs gruppieren."""
    features = build_evolution_features(
        [
            {
                "name": "meltan",
                "evolves_from": None,
                "evolution_chain_id": 400,
                "generation": 7,
            },
            {
                "name": "melmetal",
                "evolves_from": "meltan",
                "evolution_chain_id": 401,
                "generation": 7,
            },
        ]
    )

    assert features["meltan"]["evolution_chain_id"] == 400
    assert features["melmetal"]["evolution_chain_id"] == 401
    assert features["melmetal"]["evolution_family"] == "meltan"
    assert features["melmetal"]["evolution_stage"] == 1
    assert features["meltan"]["evolution_max_stage"] == 1


def test_build_evolution_features_rejects_missing_parent() -> None:
    """Unvollständige Evolutionsdaten nicht still als Basisform behandeln."""
    with pytest.raises(ValueError, match="Missing evolution parent 'eevee'"):
        build_evolution_features(
            [
                {
                    "name": "vaporeon",
                    "evolves_from": "eevee",
                    "evolution_chain_id": 30,
                    "generation": 1,
                }
            ]
        )


def test_build_evolution_features_rejects_cycle() -> None:
    """Zyklische Beziehungen mit einer verständlichen Meldung ablehnen."""
    with pytest.raises(ValueError, match="contain a cycle"):
        build_evolution_features(
            [
                {
                    "name": "alpha",
                    "evolves_from": "beta",
                    "evolution_chain_id": 40,
                    "generation": 1,
                },
                {
                    "name": "beta",
                    "evolves_from": "alpha",
                    "evolution_chain_id": 40,
                    "generation": 1,
                },
            ]
        )
