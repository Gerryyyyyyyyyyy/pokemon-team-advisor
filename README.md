# Pokémon Team Advisor

Der Pokémon Team Advisor erstellt nachvollziehbare Empfehlungen für den sechsten Platz
eines Pokémon-Teams. Dafür verbindet das Projekt eine reproduzierbare
PokéAPI-Datenpipeline, explorative und statistische Analysen, PostgreSQL, ein
transparentes Multi-Label-Rollenmodell und eine zweisprachige Streamlit-Oberfläche.

## Projektstatus

Der fachliche MVP ist umgesetzt. Die Anwendung unterstützt:

- dynamische PokéAPI-Datensammlung mit Timeouts, Retries und lokalem Raw-Data-Cache,
- reproduzierbare Aufbereitung von 1.025 Standardformen,
- EDA und versionierte SQL-Analysen auf Supabase PostgreSQL,
- eine vollständige 18-mal-18-Typenmatrix einschließlich Doppeltypen,
- ein transparentes Multi-Label-Rollenmodell mit sechs Rollen,
- ein deterministisches Top-5-Ranking für den sechsten Teamplatz,
- statistische Gruppenvergleiche, Effektstärken und Bootstrap-Konfidenzintervalle,
- eine interaktive Oberfläche mit Teamwahl, Live-Suche und defensiver Analyse sowie
- einen Sprachumschalter für Deutsch und Englisch.

Stand des Datensatz-Snapshots vom **08.08.2026**:

- 1.351 Pokémon-Ressourcen wurden aus PokéAPI ermittelt und als Rohdaten gesammelt.
- 1.025 Standardformen (`is_default = true`) wurden in
  `data/processed/pokemon.csv` aufbereitet.
- Speziesbeziehungen ergänzen Generation, Evolutionsfamilie, Stufe und Finalstatus.
- Alle 18 Typen sind vertreten; 526 Pokémon besitzen einen zweiten Typ.
- Alle 1.025 Zeilen wurden idempotent in `analytics.pokemon` geladen.
- Elf SQL-Qualitätsprüfungen bestehen für den aktuellen Snapshot.
- Die Python-Testsuite umfasst aktuell **196 bestandene Tests**.

Die Zahlen beschreiben einen reproduzierbaren Snapshot und sind nicht als dauerhaft
feste Anzahl von PokéAPI-Ressourcen zu verstehen.

## MVP-Umfang

Der MVP umfasst:

- Standardformen mit maximal zwei Typen,
- Basiswerte sowie Schwächen, Resistenzen und Immunitäten,
- transparente regelbasierte Rollen und einen Clustering-Vergleich,
- erklärbare Top-5-Empfehlungen für ein Team aus genau fünf Pokémon,
- statistische Validierung ausgewählter deskriptiver Beobachtungen,
- lokalen Raw-Data-Cache und Supabase PostgreSQL sowie
- eine deutsch- und englischsprachige Streamlit-Oberfläche.

Nicht Teil des MVP sind vollständige wettbewerbsfähige Loadouts, Items, komplexe
Fähigkeiten, EVs/IVs, Wesen, Terakristallisierung, Wetter, exakte Schadensrechnung und
Kampfsimulationen. Offensive Coverage wird erst mit echten, versionsbezogenen
Attackendaten bewertet und nicht allein aus Pokémon-Typen abgeleitet.

Alternative Formen werden **nicht aus den Rohdaten gelöscht**. Der aktuelle
Processed-Datensatz verwendet `is_default = true` als bewusst einfache MVP-Regel.
Dadurch bleiben die Rohdaten für spätere Erweiterungen erhalten.

## Voraussetzungen

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (empfohlen)
- GNU Make (optional)

## Installation

```bash
git clone https://github.com/Gerryyyyyyyyyyy/pokemon-team-advisor.git
cd pokemon-team-advisor
uv sync --locked
uv run pre-commit install
```

`uv.lock` fixiert die vollständige Abhängigkeitsmenge. Nach einer beabsichtigten
Abhängigkeitsänderung wird die Lock-Datei mit `uv lock` aktualisiert und gemeinsam mit
`pyproject.toml` committed.

### Installation unter Windows

```powershell
winget install --id=astral-sh.uv -e
uv --version
uv sync --locked
uv run pre-commit install
```

Als VS-Code-Interpreter wird anschließend `.venv\Scripts\python.exe` ausgewählt. Die
virtuelle Umgebung ist lokal und wird nicht in Git gespeichert.

### Supabase-Konfiguration

Die Anwendung verwendet Supabase als verwaltetes PostgreSQL. Kopiere die Vorlage und
trage die vollständige Verbindungs-URL aus **Supabase Dashboard → Connect** in `.env`
ein:

```powershell
Copy-Item .env.example .env
```

```dotenv
DATABASE_URL=postgresql://...
```

`.env` ist über `.gitignore` ausgeschlossen und darf niemals committed werden. Bei
fehlender lokaler IPv6-Unterstützung kann die Session-Pooler-URL verwendet werden.

## Lokaler Start

```bash
uv run streamlit run src/pokemon_team_advisor/app.py
```

Mit GNU Make steht alternativ `make run` zur Verfügung.

Die Oberfläche bietet:

- Teamwahl für bis zu fünf Pokémon,
- Live-Suche nach Name oder Pokédex-ID,
- Filter nach Typ, Generation, Entwicklungsstufe und Gesamtbasiswert,
- defensive Team- und Typenanalyse,
- erklärbare Top-5-Empfehlungen nach Auswahl von fünf Teammitgliedern sowie
- einen sitzungsgebundenen Sprachwechsel zwischen Deutsch und Englisch.

Die Live-Suche aktualisiert den lokalen Eingabewert sofort und startet die teurere
Streamlit-Neuberechnung erst nach einer kurzen Tipp-Pause. Dadurch bleiben schnelles
Schreiben und gedrücktes Backspace stabil.

Pokémon-Namen stammen weiterhin aus dem englischsprachigen Datensatz. Für Namen wie
`Glurak` statt `Charizard` ist später eine zusätzliche lokalisierte Namensspalte aus
den PokéAPI-Speziesdaten vorgesehen.

## Recommender

`recommender.py` bewertet Kandidaten für Platz sechs mit drei getrennt ausgewiesenen
Komponenten:

```text
Gesamtscore = 0,50 × defensive Ergänzung
            + 0,30 × Rollenlücke
            + 0,20 × absolute Stärke
```

- **Defensive Ergänzung** belohnt Resistenzen und Immunitäten gegen aktuelle
  Teamschwächen.
- **Rollenlücke** bevorzugt Rollenprofile, die im bestehenden Team fehlen.
- **Absolute Stärke** verhindert, dass ein klares, aber sehr schwaches Profil allein
  aufgrund seiner Rollenpassung zu hoch bewertet wird.

Standardmäßig werden nur finale Entwicklungen berücksichtigt. Bereits gewählte
Pokémon werden ausgeschlossen. Eine stabile Sortierung macht das Ranking bei
identischen Eingaben deterministisch. Die Oberfläche zeigt Gesamtscore, Teilwerte,
passende Rollen und konkret abgedeckte Gefahren für jede Empfehlung.

Die Gewichte sind eine transparente fachliche Baseline und keine objektiv optimalen
Parameter. Ohne reale Nutzerpräferenzen oder Kampfergebnisse existiert noch keine
Zielvariable, gegen die ein „bestes“ Gewicht gelernt werden könnte.

## Statistische Validierung

`statistical_analysis.py` stellt wiederverwendbare Verfahren bereit:

- Levene-Test zur Prüfung unterschiedlicher Varianzen,
- Welch-t-Test für unabhängige Gruppen,
- Hedges’ g als bias-korrigierte standardisierte Effektstärke,
- Bootstrap-Konfidenzintervalle für Mittelwertdifferenzen sowie
- Pearson- und Spearman-Korrelationen.

Das Notebook `notebooks/03_statistical_validation.ipynb` wendet diese Verfahren auf
den Snapshot an. Welch-Tests werden unabhängig vom Levene-Ergebnis verwendet, weil
sie auch bei ungleichen Varianzen und Gruppengrößen robust sind.

| Vergleich | Mittelwertdifferenz | Welch-p | Hedges’ g | 95-%-Bootstrap-KI |
|---|---:|---:|---:|---:|
| Final minus nicht final | +183,06 BST | < 0,0001 | 2,747 | [174,92; 191,48] |
| Doppeltyp minus Einzeltyp, unkontrolliert | +47,95 BST | < 0,0001 | 0,435 | [34,26; 61,71] |

Finale Entwicklungen besitzen im Snapshot erwartungsgemäß wesentlich höhere
Gesamtbasiswerte. Der sehr große Effekt beschreibt den Entwicklungsstatus; er ist
kein Beleg für einen davon unabhängigen kausalen Mechanismus.

Der rohe Doppeltypenvergleich zeigt zunächst einen moderaten Unterschied. Nach
Kontrolle für Evolutionsstufe und Finalstatus bleibt nach Bonferroni-Korrektur jedoch
nur bei finalen Pokémon auf Stufe 0 ein signifikanter Unterschied:

| Stufe | Final | Differenz Doppeltyp − Einzeltyp | Welch-p | Hedges’ g | 95-%-Bootstrap-KI | Bonferroni-signifikant |
|---:|:---:|---:|---:|---:|---:|:---:|
| 0 | nein | +9,83 | 0,1046 | 0,183 | [-1,86; 21,74] | nein |
| 0 | ja | +40,51 | 0,0029 | 0,474 | [14,96; 66,31] | ja |
| 1 | nein | −5,72 | 0,6040 | −0,095 | [-27,69; 16,62] | nein |
| 1 | ja | +2,90 | 0,5630 | 0,073 | [-6,85; 12,65] | nein |
| 2 | ja | −4,52 | 0,5697 | −0,094 | [-20,97; 10,19] | nein |

Damit ist ein zweiter Typ kein allgemeiner Stärkebonus. Der Recommender bewertet
stattdessen die konkrete defensive Ergänzung eines Typprofils.

Die Funktionen können später für echte A/B-Tests wiederverwendet werden. Der aktuelle
Datensatz enthält jedoch keine zufällige Zuweisung und keine Nutzerkonversionen;
deshalb wird bewusst kein A/B-Testergebnis simuliert oder als real ausgegeben.

## Qualitätsprüfungen

```bash
make check      # Formatprüfung, Linting, Typprüfung und Tests
make coverage   # zusätzlicher Coverage-Bericht
make format     # Formatierung und sichere Ruff-Fixes
```

Unter Windows oder ohne Make:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
```

Aktueller Stand: **196 Tests bestanden**. Ein verbindlicher Coverage-Mindestwert wird
erst nach einer stabilen Ausgangsmessung festgelegt, damit die Kennzahl nicht durch
wertlose Platzhaltertests erfüllt wird.

## Projektstruktur

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
│   ├── 01_pokemon_eda.ipynb
│   ├── 02_role_analysis.ipynb
│   └── 03_statistical_validation.ipynb
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
│   ├── i18n.py
│   ├── live_search.py
│   ├── prepare_data.py
│   ├── recommender.py
│   ├── roles.py
│   ├── statistical_analysis.py
│   ├── team_analysis.py
│   └── type_effectiveness.py
├── tests/unit/
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Datenpipeline

```text
PokéAPI → Raw-Data-Cache → Aufbereitung → data/processed/pokemon.csv
        → EDA und Supabase PostgreSQL → Typen- und Teamanalyse
        → Rollenmodell → Recommender → Streamlit
```

Die Sammlung ist wiederaufnehmbar: Bereits gecachte Ressourcen müssen bei einem
erneuten Lauf nicht erneut geladen werden. Der PostgreSQL-Import ist ebenfalls
idempotent; ein identischer zweiter Lauf verändert weder Zeilenanzahl noch
Ladezeitstempel.

Große Roh- und verarbeitete Daten bleiben außerhalb von Git. Quelle, Snapshot-Datum,
Filter und Datensatzanzahl sind deshalb hier dokumentiert. Eine spätere
Dataset-Versionierung soll zusätzlich eine maschinenlesbare Metadatendatei mit Hash
erhalten.

## EDA und SQL-Ergebnisse

Das Notebook `notebooks/01_pokemon_eda.ipynb` untersucht Datenqualität,
Basiswertverteilungen, Typenprofile, Korrelationen, Generationen und
Evolutionsstufen. Die SQL-Analysen reproduzieren zentrale Ergebnisse in PostgreSQL
und erweitern sie um kontrollierte Gruppenvergleiche.

Ausgewählte Ergebnisse:

- Wasser ist mit 154 Typzugehörigkeiten der häufigste, Eis mit 48 der seltenste Typ.
- Generation 9 besitzt mit 457,4 den höchsten mittleren Gesamtbasiswert; der Verlauf
  über Generationen ist jedoch nicht monoton.
- Innerhalb evolvierender Familien steigt der Gesamtbasiswert von Stufe 0 auf 1 im
  Mittel um 147,9 und von Stufe 1 auf 2 um 128,7 Punkte.
- Flug tritt überwiegend als Sekundärtyp auf, während Normal meist Primärtyp ist.
- Typenmittelwerte sind deskriptiv und keine kausalen Effekte. Unterschiedliche
  Anteile finaler Entwicklungen beeinflussen diese Werte deutlich.

Die Abfragen unter `sql/analyses/` enthalten Generationen-, Evolutions- und
Typenanalysen sowie eine ausführbare Qualitätssuite mit elf Prüfungen.

## PostgreSQL-Datenhaltung

Die Tabelle `analytics.pokemon` enthält 20 aufbereitete Merkmale und den zusätzlichen
Ladezeitpunkt `loaded_at`. PostgreSQL-Constraints prüfen unter anderem Typen,
Basiswerte, Basiswertsumme, Generation und Evolutionsstufen. RLS ist ohne API-Policy
aktiviert; allgemeine Schema- und Tabellenrechte wurden entzogen.

Der Import erfolgt über `database_loader.py` mit gebundenen psycopg-Parametern. Ein
Fehler rollt die vollständige Transaktion zurück. `ON CONFLICT` macht den Import
wiederholbar und aktualisiert `loaded_at` nur bei einer tatsächlichen Datenänderung.

```bash
uv run python -m pokemon_team_advisor.database_loader
```

## Rollenmodell und Clustering

`roles.py` bildet eine transparente Multi-Label-Baseline mit sechs Rollen:
physischer Angreifer, spezieller Angreifer, schneller Angreifer, physische Defensive,
spezielle Defensive und Allrounder. Ein Pokémon kann bis zu drei Rollen erhalten.
Jedes Pokémon behält mindestens ein Primärprofil; dieses Label beschreibt sein
Werteprofil und ist keine Aussage über wettbewerbsfähige Stärke.

Für jede Rolle werden zwei Werte getrennt ausgewiesen:

- `fit_score` bewertet die relative Verteilung der sechs Basiswerte.
- `strength_score` bewertet relevante absolute Werte als empirisches Perzentil.

Im Snapshot ergeben sich 1.278 Rollenzuweisungen: 791 Pokémon besitzen ein Label, 215
besitzen zwei und 19 besitzen drei. Häufigkeiten sind keine Qualitätsziele und müssen
sich wegen des Multi-Label-Ansatzes nicht zu 100 Prozent summieren.

Das Notebook `notebooks/02_role_analysis.ipynb` vergleicht die Regeln mit K-Means auf
relativen, standardisierten Werteanteilen. `k = 4` liefert den besten Kompromiss aus
Trennung, Stabilität und Clustergröße (`Silhouette = 0,200`, `ARI = 0,988`). Die
niedrige absolute Silhouette und Rollenüberlappungen sprechen gegen scharf getrennte
natürliche Klassen. Das Clustering bleibt deshalb eine explorative Validierung und
wird nicht als Produktionssignal verwendet.

## Datensatz und zeitlicher Scope

Der MVP ist ein **Snapshot des gegenwärtigen PokéAPI-Datenstands** und keine
historische Rekonstruktion einzelner Generationen.

| Merkmal | Aktueller Stand |
|---|---|
| Quelle | [PokéAPI](https://pokeapi.co/) |
| Ressourcen-Endpunkt | `/api/v2/pokemon/` |
| Ermittlung | dynamisch und paginiert |
| Snapshot-Datum | 08.08.2026 |
| Rohressourcen | 1.351 |
| Processed-Zeilen | 1.025 |
| MVP-Formfilter | `is_default = true` |
| Processed-Datei | `data/processed/pokemon.csv` |

Typen und Basiswerte bilden den aktuellen API-Stand ab. Sobald Attacken oder
Fähigkeiten Teil des Modells werden, wird eine explizite Generation beziehungsweise
`version_group` eingeführt.

## Phasen

1. **Projektgrundlage – abgeschlossen:** Struktur, Installation und Qualitätstools
2. **Datensammlung – abgeschlossen:** PokéAPI-Client, Retries, Cache und Aufbereitung
3. **EDA und SQL – abgeschlossen:** Datenqualität, Visualisierungen und PostgreSQL
4. **Typensystem – abgeschlossen:** Matrix, Doppeltypen und Team-Schwächen
5. **Rollen – abgeschlossen:** Regeln, skalierte Werte und Clustering-Vergleich
6. **Recommender – abgeschlossen:** erklärbare Scores und statistische Validierung
7. **Streamlit-MVP – abgeschlossen:** Teamwahl, Top-5-Ranking und DE/EN-Oberfläche
8. **Betrieb – offen:** Container, Deployment, Monitoring und persistente Loadouts

## Methodische Leitplanken

- Score-Gewichte sind Hypothesen und keine objektiv optimalen Parameter.
- Ohne Zielvariable wird keine künstliche Accuracy berichtet.
- Rollenpassung und absolute Rollenstärke bleiben getrennte Größen.
- Beobachtete Gruppenunterschiede werden nicht automatisch kausal interpretiert.
- Simulierte Experimentdaten werden nie als reale Nutzerbeobachtungen dargestellt.
- A/B-Tests werden erst mit zufälliger Zuweisung und einer vorab definierten
  Zielmetrik durchgeführt.
- Offensive Coverage wird erst mit echten, versionsbezogenen Attackendaten bewertet.
- Reinforcement Learning wird nur bei einer vollständigen Kampfumgebung mit
  belastbarer Belohnungsfunktion erwogen.

## Vorgemerkte Erweiterungen

- historische Typenregeln nach Generation beziehungsweise `version_group`,
- offensive Coverage mit echten Attackendaten,
- vollständiger Regressionstest für die 18-mal-18-Typenmatrix,
- Multiplikator-Legende in der Oberfläche (`0×` bis `4×`),
- lokalisierte deutsche und englische Pokémon-Namen,
- persistente Loadouts und Vergleich gespeicherter Teams sowie
- A/B-Tests nach Vorliegen realer, einwilligungsbasiert erhobener Nutzungsdaten.

## Nächster Schritt

Als Nächstes folgt Phase 8: reproduzierbarer Betrieb mit Containerisierung,
Deployment, Logging und Monitoring. Persistente Loadouts benötigen zusätzlich ein
explizites Daten- und Berechtigungskonzept. Erst nach realer Nutzung werden geeignete
Erfolgsmetriken definiert und mögliche A/B-Tests geplant.
