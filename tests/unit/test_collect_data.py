"""Unit tests for PokéAPI collection and raw caching."""

import json
from pathlib import Path

import httpx
import pytest

from pokemon_team_advisor.collect_data import (
    PokemonNotFoundError,
    cache_pokemon_response,
    collect_pokemon,
    collect_pokemon_batch,
    create_http_client,
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
    requests: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            404,
            request=request,
            json={"detail": "Not found."},
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(PokemonNotFoundError, match="missingno"):
            fetch_pokemon("missingno", client=client, sleep=delays.append)

    # 404 ist kein temporärer Fehler: Eine Anfrage genügt und es wird nicht gewartet.
    assert len(requests) == 1
    assert delays == []


def test_fetch_pokemon_retries_temporary_status_codes() -> None:
    payload = {"id": 1, "name": "bulbasaur"}
    status_codes = iter([503, 502, 200])
    requests: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(next(status_codes), request=request, json=payload)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = fetch_pokemon(
            1,
            client=client,
            retry_delay_seconds=0.5,
            sleep=delays.append,
        )

    assert result == payload
    assert len(requests) == 3
    assert delays == [0.5, 1.0]


def test_fetch_pokemon_does_not_retry_non_temporary_client_error() -> None:
    requests: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_pokemon(1, client=client, sleep=delays.append)

    assert len(requests) == 1
    assert delays == []


def test_fetch_pokemon_raises_after_last_temporary_status() -> None:
    requests: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503, request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_pokemon(
                1,
                client=client,
                max_attempts=3,
                retry_delay_seconds=0.5,
                sleep=delays.append,
            )

    assert len(requests) == 3
    assert delays == [0.5, 1.0]


def test_fetch_pokemon_retries_timeout_and_then_succeeds() -> None:
    payload = {"id": 1, "name": "bulbasaur"}
    requests: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout("Temporary timeout.", request=request)
        return httpx.Response(200, request=request, json=payload)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = fetch_pokemon(1, client=client, sleep=delays.append)

    assert result == payload
    assert len(requests) == 2
    assert delays == [0.5]


def test_fetch_pokemon_validates_retry_settings_before_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected API request: {request.url}")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="max_attempts"):
            fetch_pokemon(1, client=client, max_attempts=0)

        with pytest.raises(ValueError, match="retry_delay_seconds"):
            fetch_pokemon(1, client=client, retry_delay_seconds=-0.1)


def test_create_http_client_configures_timeout_and_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Der Test entfernt nur für seine Laufzeit automatisch gesetzte Proxy-Variablen.
    # So prüft er unsere Client-Konfiguration ohne optionale Proxy-Bibliothek.
    for variable in (
        "ALL_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "http_proxy",
        "https_proxy",
    ):
        monkeypatch.delenv(variable, raising=False)

    with create_http_client(timeout_seconds=7.5) as client:
        assert client.timeout.connect == 7.5
        assert client.timeout.read == 7.5
        assert client.timeout.write == 7.5
        assert client.timeout.pool == 7.5
        assert client.headers["User-Agent"] == "pokemon-team-advisor/0.1.0"


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


def test_collect_pokemon_batch_preserves_order_and_removes_duplicates(
    tmp_path: Path,
) -> None:
    requested_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # Das letzte nicht leere URL-Segment ist bei unserem Endpunkt die ID.
        pokemon_id = int(request.url.path.rstrip("/").split("/")[-1])
        requested_ids.append(pokemon_id)
        return httpx.Response(
            200,
            request=request,
            json={"id": pokemon_id, "name": f"pokemon-{pokemon_id}"},
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        paths = collect_pokemon_batch(
            [3, 1, 3, 2],
            client=client,
            directory=tmp_path,
        )

    assert paths == [
        tmp_path / "0003.json",
        tmp_path / "0001.json",
        tmp_path / "0002.json",
    ]
    assert requested_ids == [3, 1, 2]


def test_collect_pokemon_batch_uses_cache_for_existing_items(tmp_path: Path) -> None:
    cached_path = cache_pokemon_response(
        {"id": 1, "name": "bulbasaur"},
        directory=tmp_path,
    )
    requested_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pokemon_id = int(request.url.path.rstrip("/").split("/")[-1])
        requested_ids.append(pokemon_id)
        return httpx.Response(
            200,
            request=request,
            json={"id": pokemon_id, "name": "ivysaur"},
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        paths = collect_pokemon_batch(
            [1, 2],
            client=client,
            directory=tmp_path,
        )

    assert paths == [cached_path, tmp_path / "0002.json"]
    assert requested_ids == [2]


def test_collect_pokemon_batch_validates_all_ids_before_request(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"id": 1})

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="positive integer"):
            collect_pokemon_batch(
                [1, 0, 2],
                client=client,
                directory=tmp_path,
            )

    # Obwohl die erste ID gültig war, wurde nichts angefragt: Die vollständige
    # Validierung findet vor der Sammelschleife statt.
    assert requests == []
    assert list(tmp_path.iterdir()) == []


def test_collect_pokemon_batch_accepts_empty_iterable(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected API request: {request.url}")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        paths = collect_pokemon_batch(
            [],
            client=client,
            directory=tmp_path,
        )

    assert paths == []


def test_collect_pokemon_batch_stops_on_error_and_keeps_previous_cache(
    tmp_path: Path,
) -> None:
    requested_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pokemon_id = int(request.url.path.rstrip("/").split("/")[-1])
        requested_ids.append(pokemon_id)

        if pokemon_id == 2:
            return httpx.Response(404, request=request)

        return httpx.Response(
            200,
            request=request,
            json={"id": pokemon_id, "name": f"pokemon-{pokemon_id}"},
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(PokemonNotFoundError, match="2"):
            collect_pokemon_batch(
                [1, 2, 3],
                client=client,
                directory=tmp_path,
            )

    # Pokémon 1 bleibt als Fortschritt gespeichert. Pokémon 3 wird wegen des
    # Fail-fast-Verhaltens nach dem Fehler bei ID 2 nicht mehr angefragt.
    assert requested_ids == [1, 2]
    assert (tmp_path / "0001.json").is_file()
    assert not (tmp_path / "0003.json").exists()
