# Pokémon Team Advisor

Der Pokémon Team Advisor soll ein bestehendes Team aus fünf Pokémon analysieren und
fünf nachvollziehbar bewertete Kandidaten für den sechsten Platz vorschlagen. Das
Portfolio-Projekt verbindet Datenaufbereitung, SQL, explorative Analyse, erklärbares
Scoring und eine kleine Streamlit-Anwendung.

## Projektstatus

**Phase 1 – Projektgrundlage und Phase 2 – Datensammlung sind abgeschlossen.** Die
installierbare Paketstruktur, Entwicklungsumgebung, Qualitätsprüfungen, CI und eine
minimale Streamlit-App sind eingerichtet. Die Pokémon-Ressourcen werden dynamisch
über PokéAPI ermittelt, mit Timeouts und Retries abgerufen, lokal als unveränderte
Rohdaten gecacht und anschließend in einen tabellarischen Datensatz überführt.

Stand des Datensatz-Snapshots vom **08.08.2026**:

- 1.351 Pokémon-Ressourcen wurden aus PokéAPI ermittelt und als Rohdaten gesammelt.
- 1.025 Standardformen (`is_default = true`) wurden in `data/processed/pokemon.csv`
  aufbereitet.
- Alle 18 Typen sind vertreten; Pflichtfelder, IDs, Basiswerte und Sprites wurden auf
  Vollständigkeit und Konsistenz geprüft.
- Die Supabase-Verbindung ist eingerichtet und erfolgreich getestet. Das eigentliche
  Datenbankschema und die SQL-Analysen folgen in Phase 3.

Die Zahlen beschreiben diesen Snapshot und sind nicht als dauerhaft feste Anzahl von
PokéAPI-Ressourcen zu verstehen.

## MVP-Umfang

Geplant sind:

- Standardformen und maximal zwei Typen pro Pokémon
- Basiswerte sowie Typen-Schwächen, -Resistenzen und -Immunitäten
- transparente, zunächst regelbasierte Rollen und ein Clustering-Vergleich
- erklärbare Top-5-Empfehlungen für ein Team aus genau fünf Pokémon
- lokaler Raw-Data-Cache, Supabase PostgreSQL und eine Streamlit-Oberfläche

Nicht Teil des MVP sind Movesets, Items, komplexe Fähigkeiten, EVs/IVs, Wesen,
Terakristallisierung, Wetter, Schadensrechnung und Kampfsimulationen.

Alternative Formen werden dabei **nicht aus den Rohdaten gelöscht**. Der aktuelle
Processed-Datensatz verwendet `is_default = true` als bewusst einfache MVP-Regel.
Dadurch bleiben die Rohdaten vollständig genug, um regionale oder andere relevante
Formen später gezielter in ein erweitertes Modell aufzunehmen.

## Voraussetzungen

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (empfohlen)
- GNU Make (optional; alle Befehle lassen sich auch direkt mit `uv` ausführen)

## Installation

```bash
git clone https://github.com/Gerryyyyyyyyyyy/pokemon-team-advisor.git
cd pokemon-team-advisor
uv sync --locked
uv run pre-commit install
```

`uv.lock` fixiert die komplette aufgelöste Abhängigkeitsmenge. Die `dev`-Dependency-
Group wird von `uv` in der Entwicklungsumgebung automatisch mitinstalliert. Die
Bereiche in `pyproject.toml` dokumentieren zusätzlich, welche Hauptversionen
unterstützt werden.
Nach einer beabsichtigten Abhängigkeitsänderung wird die Lock-Datei mit `uv lock`
aktualisiert und zusammen mit `pyproject.toml` geprüft.

### Installation unter Windows

`uv` lässt sich in PowerShell über WinGet installieren:

```powershell
winget install --id=astral-sh.uv -e
```

Nach einem vollständigen Neustart von VS Code:

```powershell
uv --version
uv sync --locked
uv run pre-commit install
```

Als VS-Code-Interpreter wird anschließend `.venv\Scripts\python.exe` ausgewählt. Die
virtuelle Umgebung ist lokal und wird nicht in Git gespeichert.

### Supabase-Konfiguration

Die Anwendung verwendet Supabase als verwaltetes PostgreSQL. Kopiere die Vorlage und
trage anschließend die vollständige Verbindungs-URL aus **Supabase Dashboard → Connect**
in `.env` ein:

```powershell
Copy-Item .env.example .env
```

```dotenv
DATABASE_URL=postgresql://...
```

`.env` ist über `.gitignore` ausgeschlossen und darf niemals committed werden. Lokal
kann bei fehlender IPv6-Unterstützung die Session-Pooler-URL verwendet werden. Für ein
späteres Deployment wird die passende Verbindung anhand der Hosting-Umgebung gewählt.
Die Details beschreibt die
[Supabase-Dokumentation](https://supabase.com/docs/guides/database/connecting-to-postgres).

## Lokaler Start

```bash
uv run streamlit run src/pokemon_team_advisor/app.py
```

Mit installiertem GNU Make steht alternativ `make run` zur Verfügung.

Streamlit zeigt anschließend die lokale URL im Terminal. Die Oberfläche ist weiterhin
bewusst minimal; Team-Auswahl und Empfehlungen werden erst in den späteren Modell- und
App-Phasen integriert.

## Qualitätsprüfungen

```bash
make check      # Formatprüfung, Linting, Typprüfung und Tests
make coverage   # zusätzlicher Coverage-Bericht ohne künstlichen Start-Grenzwert
make format     # Code automatisch formatieren und sichere Ruff-Fixes anwenden
```

Unter Windows oder ohne Make können die Prüfungen direkt ausgeführt werden:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
```

Ein Coverage-Mindestwert wird eingeführt, sobald in den nächsten Phasen kritische
Geschäftslogik existiert. Dadurch wird die Kennzahl nicht mit wertlosen Platzhaltertests
aufgefüllt.

## Struktur

```text
pokemon-team-advisor/
├── .gitattributes
├── .env.example
├── .pre-commit-config.yaml
├── data/
│   ├── external/
│   ├── processed/
│   └── raw/
├── notebooks/
├── reports/figures/
├── src/pokemon_team_advisor/
│   ├── __init__.py
│   ├── app.py
│   ├── collect_data.py
│   ├── database.py
│   └── prepare_data.py
├── tests/unit/
├── Makefile
├── pyproject.toml
└── uv.lock
```

Module wie `type_chart.py`, `roles.py`, `scoring.py` und `recommender.py` werden erst
angelegt, wenn ihre jeweilige Phase beginnt. Leere Architektur-Platzhalter würden die
Navigation erschweren, ohne bereits einen technischen Vertrag zu bieten.

## Datenpipeline

```text
PokéAPI → Raw-Data-Cache → Filterung/Aufbereitung → data/processed/pokemon.csv
        → Supabase PostgreSQL → Feature Engineering → Recommendation Engine → Streamlit
```

Die Pipeline ist bis zum Processed-Datensatz implementiert. Die Sammlung ist
wiederaufnehmbar: Bereits gecachte Pokémon müssen bei einem erneuten Lauf nicht noch
einmal von PokéAPI geladen werden. Die Übernahme nach Supabase folgt mit Phase 3.

Große Roh- und verarbeitete Daten bleiben außerhalb von Git; nur kleine, gezielt
kuratierte Test-Fixtures sollen versioniert werden. Quelle, Snapshot-Datum, Filter und
Datensatzanzahl sind deshalb hier dokumentiert. Für eine spätere Dataset-Versionierung
ist zusätzlich eine maschinenlesbare Metadatendatei mit Hash vorgesehen.

## Datensatz und zeitlicher Scope

Der aktuelle MVP ist ein **Snapshot des gegenwärtigen PokéAPI-Datenstands** und keine
historische Rekonstruktion einzelner Pokémon-Generationen.

| Merkmal | Aktueller Stand |
| --- | --- |
| Quelle | [PokéAPI](https://pokeapi.co/) |
| Ressourcen-Endpunkt | `/api/v2/pokemon/` |
| Ermittlung | dynamisch und paginiert |
| Snapshot-Datum | 08.08.2026 |
| Rohressourcen | 1.351 |
| Processed-Zeilen | 1.025 |
| MVP-Formfilter | `is_default = true` |
| Processed-Datei | `data/processed/pokemon.csv` |

Die Typen und Basiswerte im Processed-Datensatz bilden daher den aktuellen Stand der
API ab. Unterschiede zwischen früheren Generationen werden im MVP nicht miteinander
vermischt. Die [PokéAPI-Dokumentation](https://pokeapi.co/docs/v2) beschreibt für eine
spätere historische Erweiterung unter anderem frühere Typen, Stats und Fähigkeiten
sowie versionsgruppenspezifische Attackeninformationen. Sobald Attacken oder
Fähigkeiten Teil des Modells werden, soll deshalb eine explizite Generation
beziehungsweise `version_group` eingeführt werden.

Wichtig: `is_default` ist eine technische MVP-Vereinfachung, keine fachliche Aussage,
dass alle ausgeschlossenen Formen irrelevant wären. Da alle ermittelten Ressourcen
im Raw-Layer erhalten bleiben, kann diese Filterregel später ohne erneuten Verlust der
Ausgangsdaten verfeinert werden.

## Phasen

1. **Projektgrundlage (abgeschlossen)** – Struktur, Installation, Qualitätstools
2. **Datensammlung (abgeschlossen)** – PokéAPI-Client, Retries, Cache, Aufbereitung
3. **EDA und SQL** – Datenqualität, Visualisierungen, Supabase-PostgreSQL-Analysen
4. **Typensystem** – Matrix, Dual-Types, Team-Schwächen, Tests
5. **Rollen** – Regeln, skalierte Werte, interpretierter Clustering-Vergleich
6. **Recommender** – erklärbare Scores, Evaluation, Sensitivitätsanalyse
7. **Streamlit-App** – Teamwahl, Analyse, Top-5-Ergebnisse
8. **Betrieb** – Docker, Deployment, Logging; A/B-Test nur bei tragfähiger Nutzung

## Methodische Leitplanken

- Score-Gewichte sind Hypothesen und keine objektiv optimalen Parameter.
- Ohne Zielvariable wird keine künstliche Accuracy berichtet.
- Clustering wird nur bei interpretierbarem Erkenntnisgewinn verwendet.
- Simulierte Experimentdaten werden nie als reale Nutzerbeobachtungen dargestellt.
- Attackendaten bleiben eine optionale, spätere Erweiterung.

## Nächster Schritt

Phase 3 beginnt mit der explorativen Datenanalyse des erzeugten
`data/processed/pokemon.csv`: Datenqualität noch einmal aus analytischer Sicht
untersuchen, Verteilungen und Zusammenhänge der Typen und Basiswerte sichtbar machen
und daraus sinnvolle SQL-Tabellen für Supabase ableiten. Erst danach folgen
Typenlogik, Rollenmodell und Empfehlungssystem.
