"""Unit tests for PokéAPI collection and raw caching."""

import json
from pathlib import Path

import httpx
import pytest

from pokemon_team_advisor.collect_data import (
    PokemonNotFoundError,
    cache_pokemon_response,
    collect_pokemon,
    fetch_pokemon,
)


def test_fetch_pokemon_returns_json_payload() -> None:
    expected = {
        "id": 1,
        "name": "bulbasaur",
        "is_default": True,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://pokeapi.co/api/v2/pokemon/1/"
        return httpx.Response(200, request=request, json=expected)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = fetch_pokemon(1, client=client)

    assert result == expected


def test_fetch_pokemon_raises_clear_error_for_missing_pokemon() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            request=request,
            json={"detail": "Not found."},
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(PokemonNotFoundError, match="missingno"):
            fetch_pokemon("missingno", client=client)


def test_fetch_pokemon_rejects_non_object_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=["unexpected"])

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="JSON object"):
            fetch_pokemon(1, client=client)


def test_cache_pokemon_response_writes_json(tmp_path: Path) -> None:
    payload = {
        "id": 1,
        "name": "bulbasaur",
        "is_default": True,
    }
    directory = tmp_path / "pokemon"

    output_path = cache_pokemon_response(payload, directory=directory)

    assert output_path == directory / "0001.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload
    assert output_path.read_text(encoding="utf-8").endswith("\n")
    assert not output_path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("invalid_id", [None, True, 0, -1, "1"])
def test_cache_pokemon_response_rejects_invalid_id(
    tmp_path: Path,
    invalid_id: object,
) -> None:
    payload: dict[str, object] = {"id": invalid_id}

    with pytest.raises(ValueError, match="positive integer"):
        cache_pokemon_response(payload, directory=tmp_path)


def test_collect_pokemon_uses_existing_cache(tmp_path: Path) -> None:
    payload = {
        "id": 1,
        "name": "bulbasaur",
        "is_default": True,
    }
    cached_path = cache_pokemon_response(payload, directory=tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected API request: {request.url}")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = collect_pokemon(
            1,
            client=client,
            directory=tmp_path,
        )

    assert result == cached_path


def test_collect_pokemon_fetches_and_caches_missing_response(tmp_path: Path) -> None:
    payload = {
        "id": 1,
        "name": "bulbasaur",
        "is_default": True,
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json=payload)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        output_path = collect_pokemon(
            1,
            client=client,
            directory=tmp_path,
        )

    assert len(requests) == 1
    assert requests[0].url == "https://pokeapi.co/api/v2/pokemon/1/"
    assert output_path == tmp_path / "0001.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload
