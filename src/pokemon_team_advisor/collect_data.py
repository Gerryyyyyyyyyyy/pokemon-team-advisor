import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import httpx

POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 0.5

# Nur Statuscodes, die typischerweise einen vorübergehenden Zustand beschreiben,
# werden wiederholt:
# - 429: Wir haben in kurzer Zeit zu viele Anfragen gesendet.
# - 500/502/503/504: Der API-Server oder ein vorgeschalteter Dienst hat ein
#   temporäres Problem.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Ein eindeutiger User-Agent macht unsere Anwendung in Server-Logs erkennbar. Das
# ist bei automatisierten API-Zugriffen eine gute Praxis.
USER_AGENT = "pokemon-team-advisor/0.1.0"

# Bibliothekscode sollte keine globale Logging-Konfiguration vornehmen. Mit einem
# Modul-Logger kann die spätere Anwendung selbst entscheiden, ob und wohin
# Warnungen geschrieben werden.
LOGGER = logging.getLogger(__name__)

# Der Alias macht sichtbar, welche Art Funktion als ``sleep`` übergeben wird. In
# Produktion ist das ``time.sleep``; Tests verwenden stattdessen ``list.append``
# und müssen dadurch nicht wirklich warten.
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
    """Die Konfiguration prüfen, bevor die erste HTTP-Anfrage gesendet wird.

    Eine ungültige Anzahl von Versuchen würde sonst dazu führen, dass die Schleife
    gar nicht ausgeführt wird. Eine negative Wartezeit würde erst später und mit
    einer weniger verständlichen Meldung in ``time.sleep`` fehlschlagen.
    """
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer.")

    # ``int`` ist hier ebenfalls erlaubt, weil beispielsweise ``0`` eine sinnvolle
    # Wartezeit in einem Test sein kann. Boolesche Werte schließen wir wie bei der
    # Pokémon-ID ausdrücklich aus.
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
    """Die Wartezeit für exponentiellen Backoff berechnen.

    Beim ersten Fehlschlag ist der Exponent null: ``0.5 * 2**0 == 0.5``.
    Beim zweiten Fehlschlag ergibt sich: ``0.5 * 2**1 == 1.0``.
    """
    # ``2.0`` statt ``2`` hält das Ergebnis auch für den statischen Typprüfer
    # eindeutig im Gleitkomma-Bereich.
    return base_delay_seconds * 2.0 ** (failed_attempt - 1)


def create_http_client(
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> httpx.Client:
    """Einen einheitlich konfigurierten HTTPX-Client erzeugen.

    Die Funktion bündelt technische Einstellungen an einer Stelle. Dadurch nutzt
    ein späterer Sammellauf nicht versehentlich an verschiedenen Stellen andere
    Timeout- oder Header-Werte.

    Der zurückgegebene Client sollte als Context Manager verwendet werden:

    ``with create_http_client() as client:``

    Args:
        timeout_seconds: Maximale Inaktivitätsdauer eines Netzwerkschritts.

    Returns:
        Einen HTTPX-Client mit Timeout, Redirect-Unterstützung und User-Agent.

    Raises:
        ValueError: Wenn der Timeout nicht größer als null ist.
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
        sleep: Funktion zum Warten. Der Standard ist ``time.sleep``; Tests können
            eine Funktion ohne echte Verzögerung einsetzen.

    Returns:
        Die vollständige JSON-Antwort als Dictionary.

    Raises:
        PokemonNotFoundError: Wenn die API mit HTTP 404 antwortet.
        httpx.HTTPStatusError: Bei anderen fehlerhaften HTTP-Statuscodes.
        httpx.TransportError: Wenn ein wiederholbarer Netzwerkfehler auch beim
            letzten Versuch auftritt.
        ValueError: Wenn die Antwort an der obersten Ebene kein JSON-Objekt ist.
    """
    _validate_retry_settings(
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    url = f"{POKEAPI_BASE_URL}/pokemon/{identifier}/"

    # ``range`` endet vor dem zweiten Grenzwert. Mit ``+ 1`` erhalten wir daher
    # verständliche Versuchsnummern von 1 bis einschließlich ``max_attempts``.
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(url)
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ) as error:
            # Zeitüberschreitungen, Netzwerkfehler und vorübergehende
            # Protokollabbrüche können beim nächsten Versuch bereits verschwunden
            # sein. Nach dem letzten Versuch geben wir den Originalfehler weiter,
            # damit der aufrufende Code Ursache und Traceback vollständig erhält.
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

        # Für 404 verwenden wir eine fachliche Exception. Dieser Fehler wird nicht
        # wiederholt, weil derselbe unbekannte Name oder dieselbe unbekannte ID bei
        # einer zweiten Anfrage mit hoher Wahrscheinlichkeit wieder scheitert.
        if response.status_code == httpx.codes.NOT_FOUND:
            raise PokemonNotFoundError(f"Pokémon '{identifier}' was not found.")

        # Nur die oben festgelegten temporären HTTP-Statuscodes lösen einen neuen
        # Versuch aus. Andere 4xx-Fehler, beispielsweise 400, weisen auf eine
        # fehlerhafte Anfrage hin und würden durch Warten nicht behoben.
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

        # Beim letzten temporären Fehler und bei allen nicht wiederholbaren
        # Fehlerstatus löst HTTPX hier eine aussagekräftige HTTPStatusError aus.
        response.raise_for_status()

        # ``response.json()`` besitzt aus Sicht des Typprüfers einen sehr allgemeinen
        # Rückgabetyp. Die Laufzeitprüfung schützt unsere Funktion vor Listen, Strings
        # oder anderen unerwarteten JSON-Werten an der obersten Ebene.
        payload: object = response.json()
        if not isinstance(payload, dict):
            raise ValueError("PokéAPI response must be a JSON object.")

        # ``cast`` verändert den Wert zur Laufzeit nicht. Es informiert nur mypy
        # darüber, dass JSON-Objektschlüssel laut JSON-Standard Strings sind.
        return cast(JsonObject, payload)

    # Dieser Zustand ist durch die vorherige Validierung von ``max_attempts`` nicht
    # erreichbar. Die explizite Exception hilft sowohl Menschen als auch mypy dabei,
    # zu erkennen, dass die Funktion in jedem realen Pfad endet.
    raise AssertionError("Unreachable retry state.")


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
