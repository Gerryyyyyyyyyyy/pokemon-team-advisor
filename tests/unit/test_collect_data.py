"""Unit tests for PokéAPI collection and raw caching."""

import json
from pathlib import Path

import httpx
import pytest

from pokemon_team_advisor.collect_data import (
    PokemonNotFoundError,
    PokemonSpeciesNotFoundError,
    PokemonTypeNotFoundError,
    cache_pokemon_response,
    cache_pokemon_species_response,
    cache_type_response,
    collect_pokemon,
    collect_pokemon_batch,
    collect_pokemon_species,
    collect_pokemon_species_batch,
    collect_type,
    collect_type_batch,
    create_http_client,
    fetch_pokemon,
    fetch_pokemon_ids,
    fetch_pokemon_species,
    fetch_pokemon_species_ids,
    fetch_type,
)


def _type_payload(name: str = "fire") -> dict[str, object]:
    """Eine kleine vollständige Type-Antwort für Collector-Tests erzeugen."""
    return {
        "id": 10,
        "name": name,
        "damage_relations": {
            "double_damage_to": [{"name": "grass"}],
            "half_damage_to": [{"name": "water"}],
            "no_damage_to": [],
        },
        "past_damage_relations": [
            {
                "generation": {"name": "generation-i"},
                "damage_relations": {},
            }
        ],
    }


def test_fetch_type_returns_complete_json_payload() -> None:
    """Aktuelle und historische Beziehungen unverändert zurückgeben."""
    expected = _type_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://pokeapi.co/api/v2/type/fire/"
        return httpx.Response(200, request=request, json=expected)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = fetch_type("fire", client=client)

    assert result == expected
    assert result["past_damage_relations"] == expected["past_damage_relations"]


def test_fetch_type_raises_clear_error_for_missing_type() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(PokemonTypeNotFoundError, match="missing-type"):
            fetch_type("missing-type", client=client)

    assert len(requests) == 1


def test_fetch_type_reuses_retry_strategy() -> None:
    status_codes = iter([503, 200])
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            next(status_codes),
            request=request,
            json=_type_payload(),
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = fetch_type("fire", client=client, sleep=delays.append)

    assert result["name"] == "fire"
    assert delays == [0.5]


def test_cache_type_response_writes_named_complete_json(tmp_path: Path) -> None:
    payload = _type_payload()
    directory = tmp_path / "types"

    output_path = cache_type_response(payload, directory=directory)

    assert output_path == directory / "fire.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload
    assert output_path.read_text(encoding="utf-8").endswith("\n")
    assert not output_path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("invalid_name", [None, "", "Fire", "../fire", "fire/water"])
def test_cache_type_response_rejects_invalid_name(
    tmp_path: Path,
    invalid_name: object,
) -> None:
    payload: dict[str, object] = {"name": invalid_name}

    with pytest.raises(ValueError, match="type name"):
        cache_type_response(payload, directory=tmp_path)


def test_collect_type_uses_existing_cache(tmp_path: Path) -> None:
    cached_path = cache_type_response(_type_payload(), directory=tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected API request: {request.url}")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = collect_type("fire", client=client, directory=tmp_path)

    assert result == cached_path


def test_collect_type_rejects_mismatched_response_name(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_type_payload("water"),
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="does not match request"):
            collect_type("fire", client=client, directory=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_collect_type_batch_preserves_order_and_removes_duplicates(
    tmp_path: Path,
) -> None:
    requested_names: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        type_name = request.url.path.rstrip("/").split("/")[-1]
        requested_names.append(type_name)
        return httpx.Response(
            200,
            request=request,
            json=_type_payload(type_name),
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        paths = collect_type_batch(
            ["water", "fire", "water", "grass"],
            client=client,
            directory=tmp_path,
        )

    assert paths == [
        tmp_path / "water.json",
        tmp_path / "fire.json",
        tmp_path / "grass.json",
    ]
    assert requested_names == ["water", "fire", "grass"]


def test_fetch_pokemon_species_returns_json_payload() -> None:
    expected = {
        "id": 2,
        "name": "ivysaur",
        "evolves_from_species": {"name": "bulbasaur"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://pokeapi.co/api/v2/pokemon-species/2/"
        return httpx.Response(200, request=request, json=expected)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = fetch_pokemon_species(2, client=client)

    assert result == expected


def test_fetch_pokemon_species_raises_clear_error_for_missing_species() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(PokemonSpeciesNotFoundError, match="missing-species"):
            fetch_pokemon_species("missing-species", client=client)

    assert len(requests) == 1


def test_cache_pokemon_species_response_writes_json(tmp_path: Path) -> None:
    payload = {"id": 2, "name": "ivysaur"}
    directory = tmp_path / "pokemon_species"

    output_path = cache_pokemon_species_response(payload, directory=directory)

    assert output_path == directory / "0002.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_collect_pokemon_species_uses_existing_cache(tmp_path: Path) -> None:
    payload = {"id": 2, "name": "ivysaur"}
    cached_path = cache_pokemon_species_response(payload, directory=tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected API request: {request.url}")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        result = collect_pokemon_species(2, client=client, directory=tmp_path)

    assert result == cached_path


def test_collect_pokemon_species_batch_preserves_order_and_removes_duplicates(
    tmp_path: Path,
) -> None:
    requested_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        species_id = int(request.url.path.rstrip("/").split("/")[-1])
        requested_ids.append(species_id)
        return httpx.Response(
            200,
            request=request,
            json={"id": species_id, "name": f"species-{species_id}"},
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        paths = collect_pokemon_species_batch(
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


def test_fetch_pokemon_species_ids_follows_pagination() -> None:
    requested_offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/pokemon-species/"
        offset = request.url.params.get("offset")
        assert offset is not None
        requested_offsets.append(offset)

        if offset == "0":
            return httpx.Response(
                200,
                request=request,
                json={
                    "count": 3,
                    "next": ("https://pokeapi.co/api/v2/pokemon-species/?limit=2&offset=2"),
                    "previous": None,
                    "results": [
                        {
                            "name": "bulbasaur",
                            "url": ("https://pokeapi.co/api/v2/pokemon-species/1/"),
                        },
                        {
                            "name": "ivysaur",
                            "url": ("https://pokeapi.co/api/v2/pokemon-species/2/"),
                        },
                    ],
                },
            )

        return httpx.Response(
            200,
            request=request,
            json={
                "count": 3,
                "next": None,
                "previous": ("https://pokeapi.co/api/v2/pokemon-species/?limit=2&offset=0"),
                "results": [
                    {
                        "name": "pikachu",
                        "url": "https://pokeapi.co/api/v2/pokemon-species/25/",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        species_ids = fetch_pokemon_species_ids(client=client, page_size=2)

    assert species_ids == [1, 2, 25]
    assert requested_offsets == ["0", "2"]


def test_fetch_pokemon_species_ids_rejects_wrong_resource_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {"url": "https://pokeapi.co/api/v2/pokemon/1/"},
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="Unexpected Pokémon species resource URL"):
            fetch_pokemon_species_ids(client=client)


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


def test_fetch_pokemon_ids_follows_pagination_and_uses_resource_urls() -> None:
    requested_offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = request.url.params.get("offset")
        assert offset is not None
        requested_offsets.append(offset)

        if offset == "0":
            return httpx.Response(
                200,
                request=request,
                json={
                    "count": 3,
                    "next": "https://pokeapi.co/api/v2/pokemon/?limit=2&offset=2",
                    "previous": None,
                    "results": [
                        {
                            "name": "bulbasaur",
                            "url": "https://pokeapi.co/api/v2/pokemon/1/",
                        },
                        {
                            "name": "deoxys-normal",
                            "url": "https://pokeapi.co/api/v2/pokemon/10001/",
                        },
                    ],
                },
            )

        return httpx.Response(
            200,
            request=request,
            json={
                "count": 3,
                "next": None,
                "previous": "https://pokeapi.co/api/v2/pokemon/?limit=2&offset=0",
                "results": [
                    {
                        "name": "charmander",
                        "url": "https://pokeapi.co/api/v2/pokemon/4/",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        pokemon_ids = fetch_pokemon_ids(client=client, page_size=2)

    # Die hohe Form-ID beweist, dass wir nicht von einem lückenlosen numerischen
    # Bereich oder einer fest verdrahteten maximalen ID ausgehen.
    assert pokemon_ids == [1, 10001, 4]
    assert requested_offsets == ["0", "2"]


def test_fetch_pokemon_ids_validates_page_size_before_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected API request: {request.url}")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="page_size"):
            fetch_pokemon_ids(client=client, page_size=0)


def test_fetch_pokemon_ids_rejects_duplicate_resource_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "count": 2,
                "next": None,
                "previous": None,
                "results": [
                    {"url": "https://pokeapi.co/api/v2/pokemon/1/"},
                    {"url": "https://pokeapi.co/api/v2/pokemon/1/"},
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="Duplicate Pokémon resource ID: 1"):
            fetch_pokemon_ids(client=client)


def test_fetch_pokemon_ids_rejects_pagination_cycle() -> None:
    first_url = "https://pokeapi.co/api/v2/pokemon/?limit=2&offset=0"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "count": 2,
                "next": first_url,
                "previous": None,
                "results": [
                    {"url": "https://pokeapi.co/api/v2/pokemon/1/"},
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="pagination contains a cycle"):
            fetch_pokemon_ids(client=client, page_size=2)


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
