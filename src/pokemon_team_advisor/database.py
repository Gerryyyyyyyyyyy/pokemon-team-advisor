"""PostgreSQL connection helpers for the Supabase database."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

DEFAULT_ENV_FILE = Path(".env")
POSTGRES_URL_PREFIXES = ("postgresql://", "postgres://")

type DatabaseConnection = psycopg.Connection[tuple[Any, ...]]


class DatabaseConfigurationError(RuntimeError):
    """Raised when the PostgreSQL connection configuration is missing or invalid."""


def _validate_database_url(value: str | None) -> str:
    """Return a usable PostgreSQL URL without exposing it in error messages."""
    database_url = value.strip() if value is not None else ""

    if not database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is missing. Copy .env.example to .env and add the "
            "Supabase connection string."
        )

    if not database_url.lower().startswith(POSTGRES_URL_PREFIXES):
        raise DatabaseConfigurationError(
            "DATABASE_URL must use the postgresql:// or postgres:// scheme."
        )

    return database_url


def get_database_url(
    *,
    env_file: Path | None = DEFAULT_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Load and validate DATABASE_URL from .env or an injected environment."""
    if env_file is not None:
        load_dotenv(dotenv_path=env_file, override=False)

    source = os.environ if environ is None else environ
    return _validate_database_url(source.get("DATABASE_URL"))


def connect_database(database_url: str | None = None) -> DatabaseConnection:
    """Open a PostgreSQL connection suitable for Supabase pooler modes."""
    validated_url = (
        get_database_url() if database_url is None else _validate_database_url(database_url)
    )

    return psycopg.connect(
        validated_url,
        autocommit=False,
        prepare_threshold=None,
    )
