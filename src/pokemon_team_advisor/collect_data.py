import json
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast

import httpx

# Eine zentrale Konstante verhindert, dass die Basis-URL an mehreren Stellen als
# sogenannter Magic String verteilt wird.
POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"

# Ein Timeout verhindert, dass die Pipeline bei einer gestörten Netzwerkverbindung
# unbegrenzt wartet. HTTPX verwendet diesen Wert für Connect-, Read-, Write- und
# Pool-Timeouts. Der Wert kann beim Erzeugen des Clients überschrieben werden.
DEFAULT_TIMEOUT_SECONDS = 10.0

# Drei Versuche bedeuten: eine ursprüngliche Anfrage und höchstens zwei
# Wiederholungen. Das ist robust gegenüber kurzen Störungen, belastet die API aber
# nicht mit einer endlosen Wiederholungsschleife.
DEFAULT_MAX_ATTEMPTS = 3

# Zwischen fehlgeschlagenen Versuchen warten wir zunächst 0,5 Sekunden. Durch den
# exponentiellen Backoff wird daraus vor dem dritten Versuch 1,0 Sekunde.
DEFAULT_RETRY_DELAY_SECONDS = 0.5

# Die PokéAPI liefert Listen standardmäßig in sehr kleinen Seiten. Für unsere
# einmalige Ressourcen-Ermittlung sind 200 Einträge pro Seite ein guter Kompromiss:
# wenige Index-Anfragen, ohne von einer künstlich riesigen Einzelseite auszugehen.
DEFAULT_RESOURCE_PAGE_SIZE = 200

# Nur Statuscodes, die typischerweise einen vorübergehenden Zustand beschreiben,
# werden wiederholt. 429 steht für zu viele Anfragen; die ausgewählten 5xx-Codes
# beschreiben temporäre Probleme bei der API oder einem vorgeschalteten Dienst.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Ein eindeutiger User-Agent macht unsere Anwendung in Server-Logs erkennbar. Das
# ist bei automatisierten API-Zugriffen eine gute Praxis.
USER_AGENT = "pokemon-team-advisor/0.1.0"

# Bibliothekscode sollte keine globale Logging-Konfiguration vornehmen. Mit einem
# Modul-Logger entscheidet später die Anwendung, ob und wohin Warnungen gelangen.
LOGGER = logging.getLogger(__name__)

# In Produktion ist der Sleeper ``time.sleep``. Tests verwenden stattdessen eine
# Funktion ohne echte Wartezeit und bleiben dadurch schnell.
type Sleeper = Callable[[float], None]

# Die PokéAPI liefert an der obersten Ebene immer ein JSON-Objekt. ``object`` ist
# hier absichtlich allgemeiner als ein konkretes Pokémon-Schema: Der Collector
# speichert die vollständige Antwort, ohne ihre verschachtelte Struktur zu deuten.
type JsonObject = dict[str, object]


class PokemonNotFoundError(LookupError):
    """Fehler für ein Pokémon, das die PokéAPI nicht kennt.

    Eine eigene Exception trennt die Fachbedeutung "Pokémon nicht gefunden" vom
    technischen HTTP-Status 404. Die Benutzeroberfläche kann diesen Fehler später
    verständlich anzeigen, ohne Details von HTTPX kennen zu müssen.
    """


def _validate_pokemon_id(value: object) -> int:
    """Eine gültige Pokémon-ID zurückgeben oder einen klaren Fehler auslösen.

    Args:
        value: Ungeprüfter Wert aus einem Funktionsargument oder API-Payload.

    Returns:
        Die geprüfte positive Ganzzahl.

    Raises:
        ValueError: Wenn der Wert keine positive Ganzzahl ist.
    """
    # ``bool`` muss separat ausgeschlossen werden: In Python ist ``bool`` eine
    # Unterklasse von ``int`` und ``isinstance(True, int)`` ergibt deshalb True.
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("Pokémon ID must be a positive integer.")

    return value


def _cache_path(pokemon_id: int, *, directory: Path) -> Path:
    """Den reproduzierbaren Cache-Pfad für ein Pokémon erzeugen.

    Das ``*`` in der Signatur erzwingt ``directory=...`` beim Aufruf. Dadurch ist
    am Aufrufort eindeutig, welche Bedeutung der zweite Parameter hat.

    Die vierstellige Formatierung sorgt für eine sinnvolle alphabetische Sortierung:
    ``0001.json``, ``0002.json``, ..., ``0150.json``.
    """
    return directory / f"{pokemon_id:04d}.json"


def _validate_retry_settings(
    *,
    max_attempts: int,
    retry_delay_seconds: float,
) -> None:
    """Die Retry-Konfiguration vor der ersten HTTP-Anfrage prüfen."""
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer.")

    if (
        not isinstance(retry_delay_seconds, (int, float))
        or isinstance(retry_delay_seconds, bool)
        or retry_delay_seconds < 0
    ):
        raise ValueError("retry_delay_seconds must be a non-negative number.")


def _retry_delay(
    *,
    failed_attempt: int,
    base_delay_seconds: float,
) -> float:
    """Die Wartezeit für exponentiellen Backoff berechnen."""
    # Beim ersten Fehlschlag: 0.5 * 2**0 = 0.5 Sekunden.
    # Beim zweiten Fehlschlag: 0.5 * 2**1 = 1.0 Sekunde.
    return base_delay_seconds * 2.0 ** (failed_attempt - 1)


def _validate_unique_pokemon_ids(pokemon_ids: Iterable[int]) -> list[int]:
    """Pokémon-IDs vollständig prüfen und Duplikate geordnet entfernen.

    Die Funktion verarbeitet das gesamte Iterable, bevor die Batch-Sammlung eine
    Netzwerkanfrage startet. Enthält die Eingabe beispielsweise ``[1, 0, 2]``, wird
    also nicht erst Pokémon 1 gespeichert und danach wegen der ungültigen 0
    abgebrochen.

    Ein ``set`` ermöglicht eine schnelle Duplikatprüfung. Die zusätzliche Liste ist
    trotzdem nötig, weil Sets keine verlässliche fachliche Reihenfolge ausdrücken.
    """
    validated_ids: list[int] = []
    seen_ids: set[int] = set()

    for pokemon_id in pokemon_ids:
        validated_id = _validate_pokemon_id(pokemon_id)

        if validated_id not in seen_ids:
            seen_ids.add(validated_id)
            validated_ids.append(validated_id)

    return validated_ids


def create_http_client(
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> httpx.Client:
    """Einen einheitlich konfigurierten HTTPX-Client erzeugen.

    Der zurückgegebene Client sollte als Context Manager verwendet werden:
    ``with create_http_client() as client:``.
    """
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive number.")

    return httpx.Client(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


def _get_with_retries(
    url: str,
    *,
    client: httpx.Client,
    max_attempts: int,
    retry_delay_seconds: float,
    sleep: Sleeper,
) -> httpx.Response:
    """Eine GET-Anfrage mit unserer zentralen Retry-Strategie ausführen.

    Sowohl ein einzelnes Pokémon als auch die paginierte Ressourcenliste benötigen
    dieselbe technische Fehlerbehandlung. Diese private Funktion verhindert, dass
    Timeout-, Backoff- und Statuscode-Regeln an zwei Stellen auseinanderlaufen.

    Die Funktion gibt auch eine endgültige Fehlerantwort zurück. Dadurch kann der
    aufrufende fachliche Code unterscheiden, ob beispielsweise ein 404 bei einem
    Pokémon als ``PokemonNotFoundError`` übersetzt werden soll.
    """
    _validate_retry_settings(
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(url)
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ) as error:
            if attempt == max_attempts:
                raise

            delay = _retry_delay(
                failed_attempt=attempt,
                base_delay_seconds=retry_delay_seconds,
            )
            LOGGER.warning(
                "Temporärer PokéAPI-Fehler %s; Versuch %s von %s in %.1f Sekunden.",
                type(error).__name__,
                attempt + 1,
                max_attempts,
                delay,
            )
            sleep(delay)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
            delay = _retry_delay(
                failed_attempt=attempt,
                base_delay_seconds=retry_delay_seconds,
            )
            LOGGER.warning(
                "PokéAPI antwortete mit HTTP %s; Versuch %s von %s in %.1f Sekunden.",
                response.status_code,
                attempt + 1,
                max_attempts,
                delay,
            )
            sleep(delay)
            continue

        return response

    # ``max_attempts`` ist vorher als mindestens 1 validiert. Dieser Zustand ist
    # deshalb nur eine Schutzklausel für Typprüfer und zukünftige Änderungen.
    raise AssertionError("Unreachable retry state.")


def _response_json_object(response: httpx.Response) -> JsonObject:
    """Den Response-Body als JSON-Objekt validieren und typisiert zurückgeben."""
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise ValueError("PokéAPI response must be a JSON object.")

    return cast(JsonObject, payload)


def fetch_pokemon(
    identifier: int | str,
    *,
    client: httpx.Client,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    sleep: Sleeper = time.sleep,
) -> JsonObject:
    """Ein Pokémon mit begrenzten Retries abrufen und unverändert zurückgeben.

    Args:
        identifier: Numerische ID oder API-Name, beispielsweise ``1`` oder
            ``"bulbasaur"``.
        client: Von außen bereitgestellter HTTPX-Client. Diese Dependency Injection
            ermöglicht schnelle Tests mit ``MockTransport`` ohne Internetzugriff.
        max_attempts: Gesamtzahl der Versuche einschließlich der ersten Anfrage.
        retry_delay_seconds: Basiswartezeit für den exponentiellen Backoff.
        sleep: Funktion zum Warten; Tests injizieren eine Funktion ohne Verzögerung.

    Returns:
        Die vollständige JSON-Antwort als Dictionary.

    Raises:
        PokemonNotFoundError: Wenn die API mit HTTP 404 antwortet.
        httpx.HTTPStatusError: Bei anderen fehlerhaften HTTP-Statuscodes.
        httpx.TransportError: Wenn ein wiederholbarer Netzwerkfehler auch beim
            letzten Versuch auftritt.
        ValueError: Wenn die Antwort an der obersten Ebene kein JSON-Objekt ist.
    """
    url = f"{POKEAPI_BASE_URL}/pokemon/{identifier}/"
    response = _get_with_retries(
        url,
        client=client,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        sleep=sleep,
    )

    # 404 ist bei einem konkreten Pokémon eine fachlich eindeutige Antwort und wird
    # deshalb in unsere eigene Exception übersetzt.
    if response.status_code == httpx.codes.NOT_FOUND:
        raise PokemonNotFoundError(f"Pokémon '{identifier}' was not found.")

    response.raise_for_status()
    return _response_json_object(response)


def _pokemon_id_from_resource_url(resource_url: object) -> int:
    """Eine numerische Pokémon-ID aus einer PokéAPI-Resource-URL lesen.

    Wir verwenden die von der API gelieferten URLs statt ``range(1, max_id)``.
    Dadurch funktionieren auch Ressourcen mit hohen Form-IDs und mögliche Lücken
    im ID-Raum, ohne dass wir sie erraten müssen.
    """
    if not isinstance(resource_url, str) or not resource_url:
        raise ValueError("Pokémon resource URL must be a non-empty string.")

    path_parts = httpx.URL(resource_url).path.strip("/").split("/")
    if len(path_parts) < 2 or path_parts[-2] != "pokemon":
        raise ValueError(f"Unexpected Pokémon resource URL: {resource_url}")

    try:
        pokemon_id = int(path_parts[-1])
    except ValueError as error:
        raise ValueError(f"Pokémon resource URL has no numeric ID: {resource_url}") from error

    return _validate_pokemon_id(pokemon_id)


def fetch_pokemon_ids(
    *,
    client: httpx.Client,
    page_size: int = DEFAULT_RESOURCE_PAGE_SIZE,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    sleep: Sleeper = time.sleep,
) -> list[int]:
    """Alle aktuell gelisteten Pokémon-Resource-IDs paginiert ermitteln.

    Die PokéAPI liefert neben Standard-Pokémon auch alternative Formen als eigene
    Pokémon-Ressourcen. Wir sammeln zunächst alle von der API gemeldeten IDs. Der
    bereits getestete ``is_default``-Filter in ``prepare_data.py`` entscheidet erst
    später, welche davon in den MVP-Datensatz gelangen.

    Die Funktion folgt dem ``next``-Link der API, prüft eine konstante Gesamtzahl
    über alle Seiten und erkennt doppelte IDs oder zyklische Pagination als
    Datenfehler. Damit wird eine unvollständige Liste nicht still akzeptiert.
    """
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        raise ValueError("page_size must be a positive integer.")

    next_url: str | None = f"{POKEAPI_BASE_URL}/pokemon/?limit={page_size}&offset=0"
    expected_count: int | None = None
    pokemon_ids: list[int] = []
    seen_ids: set[int] = set()
    visited_pages: set[str] = set()

    while next_url is not None:
        if next_url in visited_pages:
            raise ValueError(f"PokéAPI pagination contains a cycle: {next_url}")
        visited_pages.add(next_url)

        response = _get_with_retries(
            next_url,
            client=client,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            sleep=sleep,
        )
        response.raise_for_status()
        payload = _response_json_object(response)

        count = payload.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("PokéAPI resource count must be a non-negative integer.")
        if expected_count is None:
            expected_count = count
        elif count != expected_count:
            raise ValueError("PokéAPI resource count changed during pagination.")

        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("PokéAPI resource results must be a JSON list.")

        for index, raw_resource in enumerate(results):
            if not isinstance(raw_resource, dict):
                raise ValueError(f"PokéAPI resource results[{index}] must be a JSON object.")

            pokemon_id = _pokemon_id_from_resource_url(raw_resource.get("url"))
            if pokemon_id in seen_ids:
                raise ValueError(f"Duplicate Pokémon resource ID: {pokemon_id}.")

            seen_ids.add(pokemon_id)
            pokemon_ids.append(pokemon_id)

        raw_next = payload.get("next")
        if raw_next is not None and not isinstance(raw_next, str):
            raise ValueError("PokéAPI resource next link must be a string or null.")
        next_url = raw_next

    # Ein ``next = null`` allein beweist nicht, dass alle Ressourcen angekommen
    # sind. Der Abgleich mit ``count`` erkennt auch eine zu früh beendete Liste.
    if expected_count is None or len(pokemon_ids) != expected_count:
        raise ValueError(
            "PokéAPI resource list is incomplete: "
            f"expected {expected_count}, received {len(pokemon_ids)}."
        )

    return pokemon_ids


def cache_pokemon_response(
    payload: JsonObject,
    *,
    directory: Path,
) -> Path:
    """Eine PokéAPI-Antwort deterministisch und atomar als JSON speichern.

    Args:
        payload: Vollständiges JSON-Objekt eines Pokémon.
        directory: Zielverzeichnis, beispielsweise ``data/raw/pokemon``.

    Returns:
        Pfad der fertig geschriebenen Cache-Datei.

    Raises:
        ValueError: Wenn ``payload`` keine gültige positive Pokémon-ID enthält.
        TypeError: Wenn das Payload nicht als JSON serialisiert werden kann.
        OSError: Wenn Verzeichnis oder Datei nicht geschrieben werden können.
    """
    pokemon_id = _validate_pokemon_id(payload.get("id"))

    # ``parents=True`` erstellt auch fehlende übergeordnete Ordner. ``exist_ok=True``
    # macht wiederholte Aufrufe sicher, wenn das Verzeichnis schon vorhanden ist.
    directory.mkdir(parents=True, exist_ok=True)
    output_path = _cache_path(pokemon_id, directory=directory)

    # Wir schreiben zuerst in eine temporäre Datei. So ersetzt ein Prozessabbruch
    # während des Schreibens keine eventuell vorhandene, vollständige Cache-Datei.
    temporary_path = output_path.with_suffix(".json.tmp")

    # Sortierte Schlüssel und feste Einrückung erzeugen bei identischen Daten auch
    # identische Dateien. ``ensure_ascii=False`` erhält Zeichen wie "é" lesbar.
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    # Explizites UTF-8 verhindert plattformabhängige Standardkodierungen. Der letzte
    # Zeilenumbruch entspricht üblichen Textdatei-Konventionen und Pre-Commit-Regeln.
    temporary_path.write_text(f"{serialized}\n", encoding="utf-8")

    # ``replace`` macht erst die vollständig geschriebene temporäre Datei zum Cache.
    # Auf demselben Dateisystem ist dieser Austausch atomar.
    temporary_path.replace(output_path)

    return output_path


def collect_pokemon(
    pokemon_id: int,
    *,
    client: httpx.Client,
    directory: Path,
) -> Path:
    """Vorhandene Rohdaten verwenden oder fehlende Daten abrufen und speichern.

    Diese Funktion orchestriert nur die drei bereits getrennt testbaren Schritte:
    ID prüfen, Cache prüfen und bei Bedarf Abruf plus Speicherung ausführen.

    Args:
        pokemon_id: Positive numerische Pokémon-ID.
        client: HTTPX-Client für den möglichen API-Abruf.
        directory: Verzeichnis der lokalen Rohdaten.

    Returns:
        Pfad der vorhandenen oder neu geschriebenen Cache-Datei.
    """
    validated_id = _validate_pokemon_id(pokemon_id)
    cached_path = _cache_path(validated_id, directory=directory)

    # Ein Cache-Hit beendet die Funktion früh. Dadurch erfolgt bei wiederholten
    # Pipeline-Läufen keine unnötige Anfrage an die PokéAPI.
    if cached_path.is_file():
        return cached_path

    # Bei einem Cache-Miss bleiben Netzwerkzugriff und Dateischreiben in ihren
    # jeweiligen Funktionen gekapselt. Das erleichtert Tests und spätere Änderungen.
    payload = fetch_pokemon(validated_id, client=client)
    return cache_pokemon_response(payload, directory=directory)


def collect_pokemon_batch(
    pokemon_ids: Iterable[int],
    *,
    client: httpx.Client,
    directory: Path,
) -> list[Path]:
    """Mehrere Pokémon sequenziell sammeln und ihre Cache-Pfade zurückgeben.

    Diese Funktion führt absichtlich keine parallelen HTTP-Anfragen aus. Ein
    sequenzieller Ablauf ist leichter nachvollziehbar, schont die kostenlose API
    und reicht für den einmaligen Aufbau unseres MVP-Datensatzes aus.

    Args:
        pokemon_ids: Positive IDs. Duplikate werden bei erhaltener Reihenfolge
            entfernt.
        client: Gemeinsamer HTTPX-Client für alle möglicherweise nötigen Abrufe.
        directory: Zielverzeichnis der lokalen Rohdaten.

    Returns:
        Cache-Pfade in derselben Reihenfolge wie die eindeutigen Eingabe-IDs.

    Raises:
        ValueError: Wenn mindestens eine ID ungültig ist. Die Prüfung erfolgt vor
            dem ersten API-Abruf.
        PokemonNotFoundError: Wenn eine ID nicht existiert.
        httpx.HTTPError: Wenn ein HTTP- oder Netzwerkfehler endgültig fehlschlägt.

    Bereits erfolgreich gespeicherte Dateien bleiben bei einem späteren Fehler
    erhalten. Ein erneuter Lauf überspringt sie durch den bestehenden Cache und
    kann dadurch effizient fortsetzen.
    """
    validated_ids = _validate_unique_pokemon_ids(pokemon_ids)

    collected_paths: list[Path] = []
    for pokemon_id in validated_ids:
        path = collect_pokemon(
            pokemon_id,
            client=client,
            directory=directory,
        )
        collected_paths.append(path)

    return collected_paths
