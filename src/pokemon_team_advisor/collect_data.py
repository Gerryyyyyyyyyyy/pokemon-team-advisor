"""Collect and cache raw Pokémon data from PokéAPI."""

import json
from pathlib import Path
from typing import cast

import httpx

POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"

type JsonObject = dict[str, object]


class PokemonNotFoundError(LookupError):
    """Raised when the requested Pokémon does not exist."""


def _validate_pokemon_id(value: object) -> int:
    """Return a valid Pokémon ID or raise a clear error."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("Pokémon ID must be a positive integer.")

    return value


def _cache_path(pokemon_id: int, *, directory: Path) -> Path:
    """Build the deterministic cache path for one Pokémon."""
    return directory / f"{pokemon_id:04d}.json"


def fetch_pokemon(
    identifier: int | str,
    *,
    client: httpx.Client,
) -> JsonObject:
    """Fetch one Pokémon and return its unmodified JSON object."""
    response = client.get(f"{POKEAPI_BASE_URL}/pokemon/{identifier}/")

    if response.status_code == httpx.codes.NOT_FOUND:
        raise PokemonNotFoundError(f"Pokémon '{identifier}' was not found.")

    response.raise_for_status()

    payload: object = response.json()
    if not isinstance(payload, dict):
        raise ValueError("PokéAPI response must be a JSON object.")

    return cast(JsonObject, payload)


def cache_pokemon_response(
    payload: JsonObject,
    *,
    directory: Path,
) -> Path:
    """Store one PokéAPI response as deterministic JSON."""
    pokemon_id = _validate_pokemon_id(payload.get("id"))

    directory.mkdir(parents=True, exist_ok=True)
    output_path = _cache_path(pokemon_id, directory=directory)
    temporary_path = output_path.with_suffix(".json.tmp")

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    temporary_path.write_text(f"{serialized}\n", encoding="utf-8")
    temporary_path.replace(output_path)

    return output_path


def collect_pokemon(
    pokemon_id: int,
    *,
    client: httpx.Client,
    directory: Path,
) -> Path:
    """Return a cached response or fetch and cache it when missing."""
    validated_id = _validate_pokemon_id(pokemon_id)
    cached_path = _cache_path(validated_id, directory=directory)

    if cached_path.is_file():
        return cached_path

    payload = fetch_pokemon(validated_id, client=client)
    return cache_pokemon_response(payload, directory=directory)
