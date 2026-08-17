"""Unit Tests für die Ableitung von Evolutionsmerkmalen."""

import pytest

from pokemon_team_advisor.evolution import build_evolution_features


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
            "evolution_stage": 0,
            "evolution_max_stage": 2,
            "is_final_evolution": False,
            "generation": 2,
        },
        "pikachu": {
            "evolution_chain_id": 10,
            "evolution_stage": 1,
            "evolution_max_stage": 2,
            "is_final_evolution": False,
            "generation": 1,
        },
        "raichu": {
            "evolution_chain_id": 10,
            "evolution_stage": 2,
            "evolution_max_stage": 2,
            "is_final_evolution": True,
            "generation": 1,
        },
        "kangaskhan": {
            "evolution_chain_id": 20,
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
    assert features["eevee"]["is_final_evolution"] is False
    assert features["vaporeon"]["evolution_stage"] == 1
    assert features["vaporeon"]["is_final_evolution"] is True
    assert features["sylveon"]["evolution_stage"] == 1
    assert features["sylveon"]["generation"] == 6


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
