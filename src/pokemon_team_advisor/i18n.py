"""Kleine, typsichere Übersetzungsschicht für die Streamlit-Oberfläche."""

from enum import StrEnum


class Language(StrEnum):
    """Von der Oberfläche unterstützte Sprachen."""

    GERMAN = "de"
    ENGLISH = "en"


DEFAULT_LANGUAGE = Language.GERMAN
LANGUAGE_OPTIONS = ("DE", "EN")

_LANGUAGE_BY_OPTION = {
    "DE": Language.GERMAN,
    "EN": Language.ENGLISH,
}

_TRANSLATIONS: dict[Language, dict[str, str]] = {
    Language.GERMAN: {
        "intro": (
            "Stelle ein Team aus bis zu fünf Pokémon zusammen. Filtere den Pokédex, "
            "erkenne gemeinsame defensive Schwächen und erhalte eine erklärbare "
            "Empfehlung für Platz sechs."
        ),
        "loadouts_open": "Loadouts ansehen",
        "loadouts_title": "Loadouts",
        "loadouts_future": "Für eine spätere Projektphase vorgesehen",
        "loadouts_description": (
            "Hier kannst du später gespeicherte Teams öffnen, vergleichen und als "
            "Ausgangspunkt für neue Analysen verwenden."
        ),
        "loadout_save": "Loadout speichern",
        "loadout_load": "Loadout laden",
        "data_error": (
            "Die aufbereiteten Datendateien fehlen oder sind ungültig. Erzeuge zuerst "
            "die Pokémon-Daten und die Typenmatrix."
        ),
        "filters_header": "Pokédex filtern",
        "filter_type": "Typ",
        "all_types": "Alle Typen",
        "filter_generation": "Generation",
        "all_generations": "Alle Generationen",
        "filter_stage": "Entwicklungsstufe",
        "stage_all": "Alle",
        "stage_base": "Basis",
        "stage_first": "1. Entwicklung",
        "stage_second": "2. Entwicklung",
        "filter_final_only": "Nur finale Entwicklungen",
        "filter_dual_only": "Nur Pokémon mit zwei Typen",
        "filter_minimum_bst": "Mindest-Gesamtbasiswert",
        "dataset_summary": (
            "{pokemon_count} Pokémon · {type_count} Typen · lokale, schreibgeschützte Daten"
        ),
        "team_title": "Dein Team",
        "team_instruction": "Wähle fünf Pokémon als Grundlage für die Empfehlung aus.",
        "occupied_slots": "Belegte Plätze",
        "free_slots": "{count} Plätze frei",
        "one_free_slot": "1 Platz frei",
        "empty_team": "Dein Team ist noch leer. Suche unten nach dem ersten Pokémon.",
        "team_error": "Das gespeicherte Team konnte nicht sicher verarbeitet werden.",
        "total_bst": "Gesamtbasiswert",
        "final": "final",
        "not_final": "nicht final",
        "member_metadata": ("Generation {generation} · Stufe {stage}/{max_stage} · {final_status}"),
        "remove_from_team": "Aus Team entfernen",
        "remove": "Entfernen",
        "add_to_team": "Zum Team",
        "browser_metadata": "Gen. {generation} · BST {bst}",
        "defense_title": "Defensive Typenanalyse",
        "shared_weaknesses": "Gemeinsame Schwächen: {types}",
        "no_shared_weakness": "Keine gemeinsame Typenschwäche in der aktuellen Auswahl.",
        "attack_type": "Angriffstyp",
        "weak_members": "Schwache Mitglieder",
        "weaknesses": "Schwächen",
        "resistances": "Resistenzen",
        "immunities": "Immunitäten",
        "maximum_factor": "Max. Faktor",
        "coverage_title": "Vollständige defensive Abdeckung",
        "weak": "Schwach",
        "resistant": "Resistent",
        "immune": "Immun",
        "neutral": "Neutral",
        "no_recommendations": "Für dieses Team wurden keine passenden Kandidaten gefunden.",
        "recommendations_title": "Empfehlungen für Platz 6",
        "recommendations_caption": (
            "Gesamtscore: 50 % defensive Ergänzung, 30 % Rollenlücke und 20 % "
            "absolute Stärke. Standardmäßig werden nur finale Entwicklungen bewertet."
        ),
        "recommendations_explanation_title": "Wie entstehen die Empfehlungen?",
        "recommendations_explanation": (
            "Die defensive Ergänzung prüft konkrete Resistenzen und Immunitäten gegen "
            "aktuelle Teamschwächen. Die Rollenkomponente bevorzugt Profile, die im "
            "Team noch fehlen. Die Stärke verhindert, dass ein klares, aber sehr "
            "schwaches Profil automatisch zu weit oben landet."
        ),
        "recommendation_score": "Empfehlungsscore",
        "recommendation_components": (
            "Defensive Ergänzung {defense} · Rollenlücke {role} · Stärke {strength}"
        ),
        "matching_roles": "Passende Rollen: {roles}",
        "covered_threats": "Abgedeckte Gefahren: {threats}",
        "no_covered_threats": "Keine aktuelle Teamschwäche resistiert",
        "recommendations_error": "Die Empfehlungen konnten nicht sicher berechnet werden.",
        "search_title": "Pokédex durchsuchen",
        "search_label": "Name oder Pokédex-Nummer",
        "search_placeholder": "Zum Beispiel Gengar, Mr Mime oder #025",
        "sort_label": "Sortierung",
        "sort_pokedex": "Pokédex-Nummer",
        "sort_name": "Name A–Z",
        "sort_strongest": "Stärkste zuerst",
        "sort_lowest": "Niedrigster Gesamtwert",
        "filter_error": "Die Filter konnten nicht sicher verarbeitet werden.",
        "results": "Treffer",
        "results_limited": (
            "Die ersten {limit} Treffer werden angezeigt. Grenze die Suche weiter ein."
        ),
        "no_results": "Kein Pokémon passt zu dieser Suche und den aktiven Filtern.",
        "analysis_error": "Das Team konnte nicht sicher analysiert werden.",
        "role_physical_attacker": "Physischer Angreifer",
        "role_special_attacker": "Spezieller Angreifer",
        "role_fast_attacker": "Schneller Angreifer",
        "role_physical_defender": "Physische Defensive",
        "role_special_defender": "Spezielle Defensive",
        "role_all_rounder": "Allrounder",
    },
    Language.ENGLISH: {
        "intro": (
            "Build a team of up to five Pokémon. Filter the Pokédex, identify shared "
            "defensive weaknesses, and get an explainable recommendation for slot six."
        ),
        "loadouts_open": "View loadouts",
        "loadouts_title": "Loadouts",
        "loadouts_future": "Planned for a later project phase",
        "loadouts_description": (
            "Later, you will be able to open and compare saved teams and use them as a "
            "starting point for new analyses."
        ),
        "loadout_save": "Save loadout",
        "loadout_load": "Load loadout",
        "data_error": (
            "The processed data files are missing or invalid. Generate the Pokémon data "
            "and type-effectiveness matrix first."
        ),
        "filters_header": "Filter Pokédex",
        "filter_type": "Type",
        "all_types": "All types",
        "filter_generation": "Generation",
        "all_generations": "All generations",
        "filter_stage": "Evolution stage",
        "stage_all": "All",
        "stage_base": "Base",
        "stage_first": "First evolution",
        "stage_second": "Second evolution",
        "filter_final_only": "Final evolutions only",
        "filter_dual_only": "Dual-type Pokémon only",
        "filter_minimum_bst": "Minimum base stat total",
        "dataset_summary": ("{pokemon_count} Pokémon · {type_count} types · local, read-only data"),
        "team_title": "Your team",
        "team_instruction": "Choose five Pokémon as the basis for the recommendation.",
        "occupied_slots": "Occupied slots",
        "free_slots": "{count} slots available",
        "one_free_slot": "1 slot available",
        "empty_team": "Your team is empty. Search below for your first Pokémon.",
        "team_error": "The saved team could not be processed safely.",
        "total_bst": "Base stat total",
        "final": "final",
        "not_final": "not final",
        "member_metadata": ("Generation {generation} · Stage {stage}/{max_stage} · {final_status}"),
        "remove_from_team": "Remove from team",
        "remove": "Remove",
        "add_to_team": "Add to team",
        "browser_metadata": "Gen. {generation} · BST {bst}",
        "defense_title": "Defensive type analysis",
        "shared_weaknesses": "Shared weaknesses: {types}",
        "no_shared_weakness": "No shared type weakness in the current selection.",
        "attack_type": "Attack type",
        "weak_members": "Weak members",
        "weaknesses": "Weaknesses",
        "resistances": "Resistances",
        "immunities": "Immunities",
        "maximum_factor": "Max. multiplier",
        "coverage_title": "Complete defensive coverage",
        "weak": "Weak",
        "resistant": "Resistant",
        "immune": "Immune",
        "neutral": "Neutral",
        "no_recommendations": "No suitable candidates were found for this team.",
        "recommendations_title": "Recommendations for slot 6",
        "recommendations_caption": (
            "Total score: 50% defensive contribution, 30% role gap, and 20% absolute "
            "strength. Only final evolutions are evaluated by default."
        ),
        "recommendations_explanation_title": "How are recommendations calculated?",
        "recommendations_explanation": (
            "The defensive contribution checks concrete resistances and immunities "
            "against the team's current weaknesses. The role component favors profiles "
            "that are still missing from the team. Strength prevents a clear but very "
            "weak profile from ranking too highly automatically."
        ),
        "recommendation_score": "Recommendation score",
        "recommendation_components": (
            "Defensive contribution {defense} · Role gap {role} · Strength {strength}"
        ),
        "matching_roles": "Matching roles: {roles}",
        "covered_threats": "Covered threats: {threats}",
        "no_covered_threats": "Does not resist a current team weakness",
        "recommendations_error": "The recommendations could not be calculated safely.",
        "search_title": "Search Pokédex",
        "search_label": "Name or Pokédex number",
        "search_placeholder": "For example Gengar, Mr Mime, or #025",
        "sort_label": "Sort by",
        "sort_pokedex": "Pokédex number",
        "sort_name": "Name A–Z",
        "sort_strongest": "Strongest first",
        "sort_lowest": "Lowest base stat total",
        "filter_error": "The filters could not be processed safely.",
        "results": "Results",
        "results_limited": ("The first {limit} results are shown. Narrow your search to see more."),
        "no_results": "No Pokémon matches this search and the active filters.",
        "analysis_error": "The team could not be analyzed safely.",
        "role_physical_attacker": "Physical attacker",
        "role_special_attacker": "Special attacker",
        "role_fast_attacker": "Fast attacker",
        "role_physical_defender": "Physical defender",
        "role_special_defender": "Special defender",
        "role_all_rounder": "All-rounder",
    },
}

_TYPE_NAMES: dict[Language, dict[str, str]] = {
    Language.GERMAN: {
        "bug": "Käfer",
        "dark": "Unlicht",
        "dragon": "Drache",
        "electric": "Elektro",
        "fairy": "Fee",
        "fighting": "Kampf",
        "fire": "Feuer",
        "flying": "Flug",
        "ghost": "Geist",
        "grass": "Pflanze",
        "ground": "Boden",
        "ice": "Eis",
        "normal": "Normal",
        "poison": "Gift",
        "psychic": "Psycho",
        "rock": "Gestein",
        "steel": "Stahl",
        "water": "Wasser",
    },
    Language.ENGLISH: {
        "bug": "Bug",
        "dark": "Dark",
        "dragon": "Dragon",
        "electric": "Electric",
        "fairy": "Fairy",
        "fighting": "Fighting",
        "fire": "Fire",
        "flying": "Flying",
        "ghost": "Ghost",
        "grass": "Grass",
        "ground": "Ground",
        "ice": "Ice",
        "normal": "Normal",
        "poison": "Poison",
        "psychic": "Psychic",
        "rock": "Rock",
        "steel": "Steel",
        "water": "Water",
    },
}


def language_from_option(value: object) -> Language:
    """Eine manipulierte oder fehlende Auswahl sicher auf Deutsch zurückführen."""
    if not isinstance(value, str):
        return DEFAULT_LANGUAGE
    return _LANGUAGE_BY_OPTION.get(value, DEFAULT_LANGUAGE)


def text(language: Language, key: str, **values: object) -> str:
    """Einen internen UI-Schlüssel übersetzen und kontrolliert formatieren."""
    try:
        template = _TRANSLATIONS[language][key]
    except KeyError as error:
        raise ValueError(f"Unknown translation key: {key}.") from error
    return template.format(**values)


def type_name(language: Language, pokemon_type: str) -> str:
    """Einen validierten internen Typnamen für die Oberfläche lokalisieren."""
    try:
        return _TYPE_NAMES[language][pokemon_type]
    except KeyError as error:
        raise ValueError(f"Unknown Pokémon type: {pokemon_type}.") from error
