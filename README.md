# Pokémon Team Advisor

Der Pokémon Team Advisor soll ein bestehendes Team aus fünf Pokémon analysieren und
fünf nachvollziehbar bewertete Kandidaten für den sechsten Platz vorschlagen. Das
Portfolio-Projekt verbindet Datenaufbereitung, SQL, explorative Analyse, erklärbares
Scoring und eine kleine Streamlit-Anwendung.

## Projektstatus

**Phase 1 – Projektgrundlage ist abgeschlossen.** Die installierbare Paketstruktur,
eine neutrale Startseite und die lokalen Qualitätsprüfungen sind eingerichtet und
getestet. Datenabruf, Typenlogik, Rollen und Empfehlungen sind bewusst noch nicht
implementiert.

## MVP-Umfang

Geplant sind:

- Standardformen und maximal zwei Typen pro Pokémon
- Basiswerte sowie Typen-Schwächen, -Resistenzen und -Immunitäten
- transparente, zunächst regelbasierte Rollen und ein Clustering-Vergleich
- erklärbare Top-5-Empfehlungen für ein Team aus genau fünf Pokémon
- lokaler Raw-Data-Cache, Supabase PostgreSQL und eine Streamlit-Oberfläche

Nicht Teil des MVP sind Movesets, Items, komplexe Fähigkeiten, EVs/IVs, Wesen,
Terakristallisierung, Wetter, Schadensrechnung und Kampfsimulationen.

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

Streamlit zeigt anschließend die lokale URL im Terminal. In Phase 1 ist nur die
Projekt-Startseite sichtbar.

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
│   └── database.py
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
PokéAPI → Raw-Data-Cache → Validierung → verarbeiteter Datensatz → Supabase PostgreSQL
        → Feature Engineering → Recommendation Engine → Streamlit
```

Große Roh- und verarbeitete Daten bleiben außerhalb von Git; nur kleine, gezielt
kuratierte Test-Fixtures sollen versioniert werden. Spätere Datensätze erhalten eine
Metadatendatei mit Abrufdatum, Quelle, Endpunkt, Filtern, Datensatzanzahl und Hash.

## Phasen

1. **Projektgrundlage** – Struktur, Installation, Qualitätstools
2. **Datensammlung** – PokéAPI-Client, lokaler Cache, Validierung
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

Phase 2 beginnt mit einem kleinen, getesteten PokéAPI-Client: Timeout,
Wiederholungsstrategie, lokaler Rohdaten-Cache und Abruf weniger Standardformen als
technischer Probelauf. Erst danach wird die vollständige Sammlung gestartet.
