# Pokémon Team Advisor

Der Pokémon Team Advisor soll ein bestehendes Team aus fünf Pokémon analysieren und
fünf nachvollziehbar bewertete Kandidaten für den sechsten Platz vorschlagen. Das
Portfolio-Projekt verbindet Datenaufbereitung, SQL, explorative Analyse, erklärbares
Scoring und eine kleine Streamlit-Anwendung.

## Projektstatus

**Phase 1 – Projektgrundlage.** Aktuell stehen die installierbare Paketstruktur, eine
neutrale Startseite und die lokalen Qualitätsprüfungen. Datenabruf, Typenlogik, Rollen
und Empfehlungen sind bewusst noch nicht implementiert.

## MVP-Umfang

Geplant sind:

- Standardformen und maximal zwei Typen pro Pokémon
- Basiswerte sowie Typen-Schwächen, -Resistenzen und -Immunitäten
- transparente, zunächst regelbasierte Rollen und ein Clustering-Vergleich
- erklärbare Top-5-Empfehlungen für ein Team aus genau fünf Pokémon
- lokale Datenhaltung, DuckDB-Auswertungen und eine Streamlit-Oberfläche

Nicht Teil des MVP sind Movesets, Items, komplexe Fähigkeiten, EVs/IVs, Wesen,
Terakristallisierung, Wetter, Schadensrechnung und Kampfsimulationen.

## Voraussetzungen

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (empfohlen)
- GNU Make (optional; alle Befehle lassen sich auch direkt mit `uv` ausführen)

## Installation

```bash
git clone <repository-url>
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

## Lokaler Start

```bash
make run
```

Ohne Make:

```bash
uv run streamlit run src/pokemon_team_advisor/app.py
```

Streamlit zeigt anschließend die lokale URL im Terminal. In Phase 1 ist nur die
Projekt-Startseite sichtbar.

## Qualitätsprüfungen

```bash
make check      # Formatprüfung, Linting, Typprüfung und Tests
make coverage   # zusätzlicher Coverage-Bericht ohne künstlichen Start-Grenzwert
make format     # Code automatisch formatieren und sichere Ruff-Fixes anwenden
```

Ein Coverage-Mindestwert wird eingeführt, sobald in den nächsten Phasen kritische
Geschäftslogik existiert. Dadurch wird die Kennzahl nicht mit wertlosen Platzhaltertests
aufgefüllt.

## Struktur

```text
pokemon-team-advisor/
├── data/
│   ├── external/
│   ├── processed/
│   └── raw/
├── notebooks/
├── reports/figures/
├── src/pokemon_team_advisor/
│   ├── __init__.py
│   └── app.py
├── tests/unit/
├── Makefile
├── pyproject.toml
└── uv.lock
```

Module wie `type_chart.py`, `roles.py`, `scoring.py` und `recommender.py` werden erst
angelegt, wenn ihre jeweilige Phase beginnt. Leere Architektur-Platzhalter würden die
Navigation erschweren, ohne bereits einen technischen Vertrag zu bieten.

## Geplante Datenpipeline

```text
PokéAPI → Raw-Data-Cache → Validierung → verarbeiteter Datensatz → DuckDB
        → Feature Engineering → Recommendation Engine → Streamlit
```

Große Roh- und verarbeitete Daten bleiben außerhalb von Git; nur kleine, gezielt
kuratierte Test-Fixtures sollen versioniert werden. Spätere Datensätze erhalten eine
Metadatendatei mit Abrufdatum, Quelle, Endpunkt, Filtern, Datensatzanzahl und Hash.

## Phasen

1. **Projektgrundlage** – Struktur, Installation, Qualitätstools
2. **Datensammlung** – PokéAPI-Client, lokaler Cache, Validierung
3. **EDA und SQL** – Datenqualität, Visualisierungen, DuckDB-Analysen
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

Phase 2 beginnt mit einem kleinen, getesteten PokéAPI-Client: Timeout,
Wiederholungsstrategie, lokaler Rohdaten-Cache und Abruf weniger Standardformen als
technischer Probelauf. Erst danach wird die vollständige Sammlung gestartet.
