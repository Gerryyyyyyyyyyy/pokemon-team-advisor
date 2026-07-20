"""Pokémon-Rohdaten von der PokéAPI abrufen und lokal zwischenspeichern.

Dieses Modul ist ausschließlich für die Datensammlung zuständig. Es verändert
keine Werte aus der API-Antwort.
"""

import json
from pathlib import Path
from typing import cast

import httpx

POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"

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


# Prüft ob die ID valide ist
def _validate_pokemon_id(value: object) -> int:

    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("Pokémon ID must be a positive integer.")

    return value


# Baue den Pfad
def _cache_path(pokemon_id: int, *, directory: Path) -> Path:

    return directory / f"{pokemon_id:04d}.json"


# Pokemon abfragen und seine JSON zurückgeben
def fetch_pokemon(
    identifier: int | str,
    *,
    client: httpx.Client,
) -> JsonObject:

    response = client.get(f"{POKEAPI_BASE_URL}/pokemon/{identifier}/")

    # Für 404 verwenden wir eine fachliche Exception. Dieser Fehler wird nicht
    # wiederholt, weil ein identischer zweiter Abruf voraussichtlich ebenso scheitert.
    if response.status_code == httpx.codes.NOT_FOUND:
        raise PokemonNotFoundError(f"Pokémon '{identifier}' was not found.")

    # Alle übrigen 4xx- und 5xx-Antworten werden nicht stillschweigend als gültige
    # Daten weitergereicht. Eine Retry-Strategie für temporäre Fehler folgt separat.
    response.raise_for_status()

    # ``response.json()`` besitzt aus Sicht des Typprüfers einen sehr allgemeinen
    # Rückgabetyp. Die Laufzeitprüfung schützt unsere Funktion vor Listen, Strings
    # oder anderen unerwarteten JSON-Werten an der obersten Ebene.
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise ValueError("PokéAPI response must be a JSON object.")

    # ``cast`` verändert den Wert zur Laufzeit nicht. Es informiert nur mypy darüber,
    # dass JSON-Objektschlüssel laut JSON-Standard Strings sind.
    return cast(JsonObject, payload)


# API Antwort speichern
def cache_pokemon_response(
    payload: JsonObject,
    *,
    directory: Path,
) -> Path:

    # Validiere die ID
    pokemon_id = _validate_pokemon_id(payload.get("id"))

    # Erstelle in DIR für die Pokemon
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


# Vorhandene Rohdaten verwenden oder fehlende Daten abrufen und speichern.
def collect_pokemon(
    pokemon_id: int,
    *,
    client: httpx.Client,
    directory: Path,
) -> Path:

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
