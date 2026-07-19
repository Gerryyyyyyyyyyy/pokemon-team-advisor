"""Basic tests for the phase-one package scaffold."""

from pokemon_team_advisor import __version__


def test_package_exposes_version() -> None:
    """Keep package metadata discoverable for later releases."""
    assert __version__ == "0.1.0"
