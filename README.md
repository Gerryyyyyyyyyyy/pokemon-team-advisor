# Pokémon Team Advisor

Der Pokémon Team Advisor analysiert die defensive Typenabdeckung eines Pokémon-Teams.
Die Anwendung verbindet eine reproduzierbare PokéAPI-Datenpipeline, explorative
Analyse, PostgreSQL und eine interaktive Streamlit-Oberfläche. Im nächsten
Entwicklungsschritt werden Rollenmerkmale und anschließend nachvollziehbare
Empfehlungen für einen weiteren Teamplatz ergänzt.

## Projektstatus

**Die Projektgrundlage, Datensammlung, EDA mit SQL sowie das Typensystem sind
abgeschlossen.** Die Pokémon-Ressourcen werden dynamisch über PokéAPI ermittelt, mit
Timeouts und Retries abgerufen, lokal als unveränderte Rohdaten gecacht und
anschließend in einen analysierbaren Datensatz überführt. Die Streamlit-App enthält
bereits Teamwahl, Live-Suche, Filter und defensive Typenanalyse; Rollenmodell und
Kandidatenranking folgen in den nächsten Phasen.

Stand des Datensatz-Snapshots vom **08.08.2026**:

- 1.351 Pokémon-Ressourcen wurden aus PokéAPI ermittelt und als Rohdaten gesammelt.
- 1.025 Standardformen (`is_default = true`) wurden in `data/processed/pokemon.csv`
  aufbereitet.
- Speziesbeziehungen ergänzen Generation, Evolutionsfamilie, Stufe und Finalstatus.
- Alle 18 Typen sind vertreten; eine vollständige 18-mal-18-Typenmatrix bildet
  Schwächen, Resistenzen und Immunitäten einschließlich Doppeltypen ab.
- Alle 1.025 Zeilen wurden idempotent in `analytics.pokemon` auf Supabase PostgreSQL
  geladen und dort erneut auf Eindeutigkeit und Konsistenz geprüft.
- Das Datenbankschema besitzt fachliche Constraints, Row Level Security und keine
  öffentlichen Zugriffsrichtlinien.

Die Zahlen beschreiben diesen Snapshot und sind nicht als dauerhaft feste Anzahl von
PokéAPI-Ressourcen zu verstehen.

## MVP-Umfang

Der geplante MVP umfasst:

- Standardformen und maximal zwei Typen pro Pokémon
- Basiswerte sowie Typen-Schwächen, -Resistenzen und -Immunitäten
- transparente, zunächst regelbasierte Rollen und ein Clustering-Vergleich
- erklärbare Top-5-Empfehlungen für ein Team aus genau fünf Pokémon
- lokaler Raw-Data-Cache, Supabase PostgreSQL und eine Streamlit-Oberfläche

Nicht Teil des ersten MVP sind vollständige wettbewerbsfähige Loadouts, Items,
komplexe Fähigkeiten, EVs/IVs, Wesen, Terakristallisierung, Wetter, exakte
Schadensrechnung und Kampfsimulationen. Eine spätere offensive Bewertung soll echte,
versionsbezogene Attackendaten verwenden und nicht nur vom Pokémon-Typ auf mögliche
Attacken schließen.

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

Streamlit zeigt anschließend die lokale URL im Terminal. Die Oberfläche bietet eine
Live-Suche nach Name oder Pokédex-ID, Filter nach Typ, Generation, Entwicklungsstufe
und Basiswerten, eine Kartenansicht zur Teamwahl und die defensive Analyse gemeinsamer
Schwächen. Die Loadout-Ansicht ist als klar gekennzeichnete Vorschau vorhanden;
Empfehlungen werden erst nach Rollen- und Scoringmodell aktiviert.

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

Die vorhandene Geschäftslogik ist durch Unit Tests abgedeckt. Ein verbindlicher
Coverage-Mindestwert wird erst nach einer stabilen Ausgangsmessung festgelegt, damit
die Kennzahl nicht durch wertlose Platzhaltertests erfüllt wird.

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
├── sql/
│   ├── analyses/
│   └── migrations/
├── src/pokemon_team_advisor/
│   ├── __init__.py
│   ├── app.py
│   ├── collect_data.py
│   ├── database.py
│   ├── database_loader.py
│   ├── evolution.py
│   ├── live_search.py
│   ├── prepare_data.py
│   ├── team_analysis.py
│   └── type_effectiveness.py
├── tests/unit/
├── Makefile
├── pyproject.toml
└── uv.lock
```

Zukünftige Rollen- und Recommender-Module werden erst angelegt, wenn ihr fachlicher
Vertrag durch Tests beschrieben wird. Leere Architektur-Platzhalter würden die
Navigation erschweren, ohne bereits einen Nutzen zu bieten.

## Datenpipeline

```text
PokéAPI → Raw-Data-Cache → Filterung/Aufbereitung → data/processed/pokemon.csv
        → EDA und Supabase PostgreSQL → Typen- und Teamanalyse → Streamlit
        → Rollenmodell und Recommender (nächste Phasen)
```

Die Pipeline ist bis zur SQL- und defensiven Teamanalyse implementiert. Die Sammlung
ist wiederaufnehmbar: Bereits gecachte Ressourcen müssen bei einem erneuten Lauf nicht
noch einmal von PokéAPI geladen werden. Der PostgreSQL-Import ist ebenfalls
idempotent; ein identischer zweiter Lauf verändert weder Zeilenanzahl noch
Ladezeitstempel.

Große Roh- und verarbeitete Daten bleiben außerhalb von Git; nur kleine, gezielt
kuratierte Test-Fixtures sollen versioniert werden. Quelle, Snapshot-Datum, Filter und
Datensatzanzahl sind deshalb hier dokumentiert. Für eine spätere Dataset-Versionierung
ist zusätzlich eine maschinenlesbare Metadatendatei mit Hash vorgesehen.

## EDA und SQL-Ergebnisse

Das Notebook `notebooks/01_pokemon_eda.ipynb` untersucht Datenqualität,
Basiswertverteilungen, Typenprofile, Korrelationen, Generationen und
Evolutionsstufen. Die SQL-Analysen reproduzieren zentrale Ergebnisse in PostgreSQL
und erweitern sie um kontrollierte Gruppenvergleiche.

Ausgewählte Ergebnisse des aktuellen Snapshots:

- Wasser ist mit 154 Typzugehörigkeiten der häufigste, Eis mit 48 der seltenste Typ.
- Generation 9 besitzt mit 457,4 den höchsten mittleren Gesamtbasiswert; der Verlauf
  über die Generationen ist jedoch nicht monoton.
- Innerhalb evolvierender Familien steigt der Gesamtbasiswert von Stufe 0 auf 1 im
  Mittel um 147,9 und von Stufe 1 auf 2 um 128,7 Punkte.
- Der zunächst sichtbare Basiswertvorteil von Doppeltypen wird größtenteils durch
  Evolutionsstufe und Finalstatus erklärt. Innerhalb vergleichbarer Gruppen liegt die
  Differenz meistens nur zwischen −5,7 und +9,8 Punkten.
- Flug tritt überwiegend als Sekundärtyp auf, während Normal meist Primärtyp ist.
- Typenmittelwerte sind deskriptiv und keine kausalen Effekte. Unterschiedliche
  Anteile finaler Entwicklungen beeinflussen diese Werte deutlich.

Die Datenbankänderungen liegen versioniert in `sql/migrations/`. Die Abfragen unter
`sql/analyses/` enthalten Generationen-, Evolutions- und Typenanalysen sowie eine
ausführbare Qualitätssuite mit elf Prüfungen. Alle Prüfungen bestehen für den
aktuellen Snapshot.

## PostgreSQL-Datenhaltung

Die Tabelle `analytics.pokemon` enthält die 20 aufbereiteten Merkmale und den
zusätzlichen Ladezeitpunkt `loaded_at`. PostgreSQL-Constraints prüfen unter anderem
Typen, Basiswerte, Basiswertsumme, Generation und Evolutionsstufen. Das Schema ist
nicht öffentlich freigegeben; RLS ist ohne API-Policy aktiviert und die allgemeinen
Schema- und Tabellenrechte wurden entzogen.

Der Import erfolgt über `database_loader.py` mit gebundenen psycopg-Parametern. Ein
Fehler rollt die vollständige Transaktion zurück. `ON CONFLICT` macht den Import
wiederholbar und aktualisiert `loaded_at` nur, wenn sich ein Datensatz tatsächlich
geändert hat.

Nach Ausführung der nummerierten Migrationen lässt sich der validierte CSV-Snapshot
mit folgendem Befehl übertragen:

```bash
uv run python -m pokemon_team_advisor.database_loader
```

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
3. **EDA und SQL (abgeschlossen)** – Datenqualität, Visualisierungen,
   Supabase-PostgreSQL-Analysen
4. **Typensystem (abgeschlossen)** – Matrix, Dual-Types, Team-Schwächen, Tests
5. **Rollen** – Regeln, skalierte Werte, interpretierter Clustering-Vergleich
6. **Recommender** – erklärbare Scores, Evaluation, Sensitivitätsanalyse
7. **Streamlit-App (teilweise umgesetzt)** – Teamwahl und Analyse vorhanden,
   Top-5-Ergebnisse folgen mit dem Recommender
8. **Betrieb** – Docker, Deployment, Logging; A/B-Test nur bei tragfähiger Nutzung

## Methodische Leitplanken

- Score-Gewichte sind Hypothesen und keine objektiv optimalen Parameter.
- Ohne Zielvariable wird keine künstliche Accuracy berichtet.
- Clustering wird nur bei interpretierbarem Erkenntnisgewinn verwendet.
- Simulierte Experimentdaten werden nie als reale Nutzerbeobachtungen dargestellt.
- Offensive Coverage wird erst mit echten, versionsbezogenen Attackendaten bewertet.
- Reinforcement Learning wird nur erwogen, falls später eine vollständige
  Kampfumgebung mit belastbarer Belohnungsfunktion entsteht.

## Nächster Schritt

Phase 5 beginnt mit einem transparenten Rollenmodell. Dafür werden skalierte
Basiswerte und fachliche Regeln als erklärbare Baseline definiert. Ein ergänzender
Clustering-Vergleich wird nur übernommen, wenn die Gruppen stabil sind und gegenüber
den Regeln einen interpretierbaren Mehrwert liefern. Erst danach kombiniert der
Recommender defensive Abdeckung, offensive Coverage und Rollenpassung zu getrennt
ausgewiesenen Teilwerten.
