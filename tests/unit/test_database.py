"""Unit tests for Supabase PostgreSQL configuration."""

from pathlib import Path

import pytest

from pokemon_team_advisor.database import (
    DatabaseConfigurationError,
    connect_database,
    get_database_url,
)


def test_get_database_url_reads_injected_environment() -> None:
    expected = "postgresql://user:password@example.test:5432/postgres"

    result = get_database_url(
        env_file=None,
        environ={"DATABASE_URL": f"  {expected}  "},
    )

    assert result == expected


def test_get_database_url_rejects_missing_value() -> None:
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is missing"):
        get_database_url(env_file=None, environ={})


def test_get_database_url_rejects_non_postgres_scheme() -> None:
    with pytest.raises(DatabaseConfigurationError, match="postgresql://"):
        get_database_url(
            env_file=None,
            environ={"DATABASE_URL": "https://example.supabase.co"},
        )


def test_get_database_url_can_load_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://user:password@example.test/postgres\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    result = get_database_url(env_file=env_file)

    assert result == "postgresql://user:password@example.test/postgres"


def test_connect_database_passes_safe_pooler_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_connection = object()
    calls: dict[str, object] = {}

    def fake_connect(conninfo: str, **kwargs: object) -> object:
        calls["conninfo"] = conninfo
        calls["kwargs"] = kwargs
        return expected_connection

    monkeypatch.setattr("pokemon_team_advisor.database.psycopg.connect", fake_connect)

    result = connect_database("postgresql://user:password@example.test/postgres")

    assert result is expected_connection
    assert calls == {
        "conninfo": "postgresql://user:password@example.test/postgres",
        "kwargs": {"autocommit": False, "prepare_threshold": None},
    }
