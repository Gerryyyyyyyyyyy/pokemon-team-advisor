"""Interaktive Streamlit-Oberfläche für Teamanalyse und Empfehlungen.

Die Oberfläche liest ausschließlich vorbereitete lokale CSV-Dateien. Sie führt
keine SQL-Abfragen aus, schreibt keine Nutzereingaben und übergibt keine freie
Eingabe an Dateipfade, HTML oder externe Dienste.
"""

from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import pandas as pd  # type: ignore[import-untyped]
import streamlit as st

from pokemon_team_advisor.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_OPTIONS,
    Language,
    language_from_option,
    text,
    type_name,
)
from pokemon_team_advisor.live_search import live_search_input
from pokemon_team_advisor.recommender import Recommendation, recommend_team_members
from pokemon_team_advisor.roles import Role
from pokemon_team_advisor.team_analysis import (
    analyze_team_defense,
    summarize_team_weaknesses,
)
from pokemon_team_advisor.type_effectiveness import (
    VALID_SINGLE_TYPE_MULTIPLIERS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POKEMON_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "pokemon.csv"
TYPE_CHART_PATH = PROJECT_ROOT / "data" / "processed" / "type_effectiveness.csv"

EXPECTED_TYPES = frozenset(
    {
        "bug",
        "dark",
        "dragon",
        "electric",
        "fairy",
        "fighting",
        "fire",
        "flying",
        "ghost",
        "grass",
        "ground",
        "ice",
        "normal",
        "poison",
        "psychic",
        "rock",
        "steel",
        "water",
    }
)

REQUIRED_POKEMON_COLUMNS = frozenset(
    {
        "id",
        "name",
        "species_name",
        "type_1",
        "type_2",
        "base_stat_total",
        "sprite_url",
        "generation",
        "evolution_stage",
        "evolution_max_stage",
        "is_final_evolution",
    }
)

RECOMMENDER_POKEMON_COLUMNS = frozenset(
    {
        "id",
        "name",
        "type_1",
        "type_2",
        "hp",
        "attack",
        "defense",
        "special_attack",
        "special_defense",
        "speed",
        "base_stat_total",
        "is_final_evolution",
    }
)

ROLE_TEXT_KEYS = {
    Role.PHYSICAL_ATTACKER: "role_physical_attacker",
    Role.SPECIAL_ATTACKER: "role_special_attacker",
    Role.FAST_ATTACKER: "role_fast_attacker",
    Role.PHYSICAL_DEFENDER: "role_physical_defender",
    Role.SPECIAL_DEFENDER: "role_special_defender",
    Role.ALL_ROUNDER: "role_all_rounder",
}


class RecommendationPresentation(TypedDict):
    """Sicher formatierte Erklärung für eine Empfehlungskarte."""

    score: str
    components: str
    roles: str
    threats: str


# Nur Sprites aus dem bekannten PokéAPI-Repository werden im Browser angezeigt.
# Dadurch kann ein manipulierter CSV-Eintrag keine beliebige Tracking- oder
# unsichere URL in die Oberfläche einschleusen.
ALLOWED_SPRITE_HOST = "raw.githubusercontent.com"
ALLOWED_SPRITE_PATH_PREFIX = "/PokeAPI/sprites/"

# Der Browser zeigt nie den gesamten Datensatz gleichzeitig. Das hält die
# Oberfläche schnell und verhindert eine unübersichtliche Wand aus 1.025 Karten.
MAX_VISIBLE_RESULTS = 24
TEAM_SESSION_KEY = "selected_team_names"
LANGUAGE_SESSION_KEY = "interface_language"

SORT_OPTIONS = {
    "Pokédex-Nummer": ("id", True),
    "Name A–Z": ("name", True),
    "Stärkste zuerst": ("base_stat_total", False),
    "Niedrigster Gesamtwert": ("base_stat_total", True),
}

SORT_TEXT_KEYS = {
    "Pokédex-Nummer": "sort_pokedex",
    "Name A–Z": "sort_name",
    "Stärkste zuerst": "sort_strongest",
    "Niedrigster Gesamtwert": "sort_lowest",
}


@st.cache_data(show_spinner=False)
def load_pokemon_data(path: Path) -> pd.DataFrame:
    """Den lokalen Processed-Datensatz laden und sein UI-Schema validieren."""
    if not path.is_file():
        raise FileNotFoundError(path)

    pokemon = pd.read_csv(path)
    missing_columns = REQUIRED_POKEMON_COLUMNS.difference(pokemon.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Processed Pokémon data is missing columns: {missing}.")

    if pokemon.empty or len(pokemon) > 5000:
        raise ValueError("Processed Pokémon data has an unexpected size.")

    if not pokemon["name"].is_unique:
        raise ValueError("Processed Pokémon names must be unique.")

    dataset_types = set(pokemon["type_1"].dropna().astype(str)) | set(
        pokemon["type_2"].dropna().astype(str)
    )
    unexpected_types = dataset_types.difference(EXPECTED_TYPES)
    if unexpected_types:
        unexpected = ", ".join(sorted(unexpected_types))
        raise ValueError(f"Processed Pokémon data contains unknown types: {unexpected}.")

    return pokemon.sort_values("id").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_type_chart(path: Path) -> dict[str, dict[str, float]]:
    """Die lokale 18-mal-18-Typenmatrix validieren und als Dictionary laden."""
    if not path.is_file():
        raise FileNotFoundError(path)

    matrix = pd.read_csv(path, index_col="attacking_type")
    matrix.index = matrix.index.map(str)
    matrix.columns = matrix.columns.map(str)

    if not matrix.index.is_unique:
        raise ValueError("Type effectiveness matrix must have unique rows.")

    if set(matrix.index) != EXPECTED_TYPES or set(matrix.columns) != EXPECTED_TYPES:
        raise ValueError("Type effectiveness matrix must contain the 18 expected types.")

    chart: dict[str, dict[str, float]] = {}

    for attacking_type in sorted(EXPECTED_TYPES):
        row: dict[str, float] = {}

        for defending_type in sorted(EXPECTED_TYPES):
            multiplier = float(matrix.loc[attacking_type, defending_type])
            if multiplier not in VALID_SINGLE_TYPE_MULTIPLIERS:
                raise ValueError(
                    f"Invalid type multiplier for '{attacking_type}' against '{defending_type}'."
                )

            row[defending_type] = multiplier

        chart[attacking_type] = row

    return chart


def format_name(name: str) -> str:
    """Einen PokéAPI-Namen ohne HTML für die Oberfläche lesbarer darstellen."""
    return name.replace("-", " ").title()


def safe_sprite_url(value: object) -> str | None:
    """Nur HTTPS-Sprites aus dem festgelegten PokéAPI-Repository akzeptieren."""
    if not isinstance(value, str) or not value:
        return None

    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != ALLOWED_SPRITE_HOST
        or parsed.port is not None
        or not parsed.path.startswith(ALLOWED_SPRITE_PATH_PREFIX)
    ):
        return None

    return value


def _integer_value(value: object, *, field: str) -> int:
    """Einen tabellarischen Ganzzahlwert ohne stilles Abschneiden lesen."""
    text = str(value)
    if not text.isdigit():
        raise ValueError(f"Field '{field}' must be a non-negative integer.")
    return int(text)


def _boolean_value(value: object, *, field: str) -> bool:
    """Einen von pandas gelesenen booleschen Wert eindeutig interpretieren."""
    text = str(value)
    if text == "True":
        return True
    if text == "False":
        return False
    raise ValueError(f"Field '{field}' must be a boolean.")


def _text_value(value: object, *, field: str) -> str:
    """Einen nicht leeren Textwert aus dem validierten Datensatz lesen."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty string.")
    return value


def pokemon_recommender_records(pokemon: pd.DataFrame) -> list[dict[str, object]]:
    """Den DataFrame sicher in Eingabedatensätze des Recommenders umwandeln."""
    missing_columns = RECOMMENDER_POKEMON_COLUMNS.difference(pokemon.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Recommender data is missing columns: {missing}.")

    records: list[dict[str, object]] = []
    seen_ids: set[int] = set()

    for row_index, (_, row) in enumerate(pokemon.iterrows()):
        pokemon_id = _integer_value(row["id"], field=f"pokemon[{row_index}].id")
        if pokemon_id in seen_ids:
            raise ValueError(f"Duplicate Pokémon id: {pokemon_id}.")
        seen_ids.add(pokemon_id)

        type_1 = _text_value(row["type_1"], field=f"pokemon[{row_index}].type_1")
        raw_type_2 = row["type_2"]
        type_2 = (
            None
            if pd.isna(raw_type_2)
            else _text_value(raw_type_2, field=f"pokemon[{row_index}].type_2")
        )
        if type_1 == type_2:
            raise ValueError("A Pokémon must not have duplicate types.")

        record: dict[str, object] = {
            "id": pokemon_id,
            "name": _text_value(row["name"], field=f"pokemon[{row_index}].name"),
            "type_1": type_1,
            "type_2": type_2,
            "is_final_evolution": _boolean_value(
                row["is_final_evolution"],
                field=f"pokemon[{row_index}].is_final_evolution",
            ),
        }
        for stat_name in (
            "hp",
            "attack",
            "defense",
            "special_attack",
            "special_defense",
            "speed",
            "base_stat_total",
        ):
            record[stat_name] = _integer_value(
                row[stat_name],
                field=f"pokemon[{row_index}].{stat_name}",
            )
        records.append(record)

    return records


def recommendation_presentation(
    recommendation: Recommendation,
    *,
    language: Language = DEFAULT_LANGUAGE,
) -> RecommendationPresentation:
    """Eine Empfehlung ohne HTML oder unkontrollierte Texte beschriften."""
    roles = " · ".join(
        text(language, ROLE_TEXT_KEYS[role]) for role in recommendation["matched_roles"]
    )
    threats = ", ".join(
        type_name(language, attacking_type) for attacking_type in recommendation["covered_threats"]
    )

    return RecommendationPresentation(
        score=f"{recommendation['total_score']:.1f} / 100",
        components=text(
            language,
            "recommendation_components",
            defense=f"{recommendation['defensive_score']:.0%}",
            role=f"{recommendation['role_score']:.0%}",
            strength=f"{recommendation['strength_score']:.0%}",
        ),
        roles=roles,
        threats=threats or text(language, "no_covered_threats"),
    )


@st.cache_data(show_spinner=False)
def cached_team_recommendations(
    team_ids: tuple[int, ...],
    pokemon_records: list[dict[str, object]],
    chart: dict[str, dict[str, float]],
) -> list[Recommendation]:
    """Empfehlungen zwischen unveränderten Streamlit-Neuläufen wiederverwenden."""
    return recommend_team_members(
        team_ids,
        pokemon_records,
        chart=chart,
        limit=5,
    )


def selected_team_records(
    pokemon: pd.DataFrame,
    selected_names: list[str],
) -> list[dict[str, object]]:
    """Nur erlaubte Datensatzoptionen für Analyse und Darstellung übernehmen."""
    pokemon_by_name = pokemon.set_index("name", drop=False)
    unknown_names = set(selected_names).difference(pokemon_by_name.index)
    if unknown_names:
        raise ValueError("Selection contains an unknown Pokémon name.")

    if len(selected_names) > 5 or len(set(selected_names)) != len(selected_names):
        raise ValueError("Selection must contain at most five unique Pokémon.")

    records: list[dict[str, object]] = []

    for name in selected_names:
        row = pokemon_by_name.loc[name]
        raw_type_2 = row["type_2"]
        type_2 = None if pd.isna(raw_type_2) else str(raw_type_2)

        records.append(
            {
                "name": name,
                "type_1": str(row["type_1"]),
                "type_2": type_2,
                "base_stat_total": _integer_value(row["base_stat_total"], field="base_stat_total"),
                "sprite_url": safe_sprite_url(row["sprite_url"]),
                "generation": _integer_value(row["generation"], field="generation"),
                "evolution_stage": _integer_value(row["evolution_stage"], field="evolution_stage"),
                "evolution_max_stage": _integer_value(
                    row["evolution_max_stage"], field="evolution_max_stage"
                ),
                "is_final_evolution": _boolean_value(
                    row["is_final_evolution"], field="is_final_evolution"
                ),
            }
        )

    return records


def type_label(
    type_1: str,
    type_2: str | None,
    *,
    language: Language = DEFAULT_LANGUAGE,
) -> str:
    """Typen als ruhige Textzeile statt als ungeprüftes HTML darstellen."""
    type_names = [type_name(language, type_1)]
    if type_2 is not None:
        type_names.append(type_name(language, type_2))
    return " · ".join(type_names)


def _normalise_search_text(value: object) -> str:
    """Namen für eine fehlertolerante, aber weiterhin wörtliche Suche normalisieren.

    PokéAPI verwendet Bindestriche in Namen wie ``mr-mime``. In der Oberfläche
    soll deshalb auch ``Mr Mime`` funktionieren. Andere Sonderzeichen behalten
    keine besondere Bedeutung; insbesondere wird der Text nicht als regulärer
    Ausdruck oder Programmcode interpretiert.
    """
    return " ".join(str(value).casefold().replace("-", " ").split())


def filter_pokemon(
    pokemon: pd.DataFrame,
    *,
    search_text: str = "",
    selected_types: list[str] | None = None,
    selected_generations: list[int] | None = None,
    evolution_stage: int | None = None,
    final_only: bool = False,
    dual_type_only: bool = False,
    minimum_base_stat_total: int = 0,
    sort_by: str = "Pokédex-Nummer",
) -> pd.DataFrame:
    """Den lokalen DataFrame anhand validierter UI-Filter eingrenzen.

    Die Funktion ist bewusst unabhängig von Streamlit. Dadurch können wir die
    komplette Such- und Filterlogik mit Unit Tests prüfen.
    """
    if len(search_text) > 80:
        raise ValueError("Search text must contain at most 80 characters.")

    types = set(selected_types or [])
    unknown_types = types.difference(EXPECTED_TYPES)
    if unknown_types:
        raise ValueError("Type filter contains an unknown Pokémon type.")

    generations = set(selected_generations or [])
    if not generations.issubset(set(range(1, 10))):
        raise ValueError("Generation filter must only contain generations 1 to 9.")

    if evolution_stage not in {None, 0, 1, 2}:
        raise ValueError("Evolution stage filter must be 0, 1, 2 or None.")

    if minimum_base_stat_total < 0:
        raise ValueError("Minimum base stat total must not be negative.")

    if sort_by not in SORT_OPTIONS:
        raise ValueError("Unknown Pokémon sort option.")

    filtered = pokemon.copy()
    query = _normalise_search_text(search_text)

    if query:
        # Mehrere Wörter müssen alle im normalisierten Namen vorkommen. Weil
        # ``regex=False`` gesetzt ist, haben Zeichen wie ``[`` oder ``*`` keine
        # technische Sonderfunktion.
        normalised_names = filtered["name"].map(_normalise_search_text)
        name_matches = pd.Series(True, index=filtered.index)
        for token in query.split():
            name_matches &= normalised_names.str.contains(token, regex=False)

        # Eine reine Zahl oder Schreibweise wie ``#025`` sucht zusätzlich exakt
        # nach der Pokédex-ID.
        possible_id = query.removeprefix("#")
        id_matches = pd.Series(False, index=filtered.index)
        if possible_id.isdigit():
            id_matches = filtered["id"].eq(int(possible_id))

        filtered = filtered[name_matches | id_matches]

    if types:
        filtered = filtered[filtered["type_1"].isin(types) | filtered["type_2"].isin(types)]

    if generations:
        filtered = filtered[filtered["generation"].isin(generations)]

    if evolution_stage is not None:
        filtered = filtered[filtered["evolution_stage"].eq(evolution_stage)]

    if final_only:
        filtered = filtered[filtered["is_final_evolution"].eq(True)]

    if dual_type_only:
        filtered = filtered[filtered["type_2"].notna()]

    filtered = filtered[filtered["base_stat_total"].ge(minimum_base_stat_total)]

    sort_column, ascending = SORT_OPTIONS[sort_by]
    return filtered.sort_values(
        [sort_column, "id"],
        ascending=[ascending, True],
    ).reset_index(drop=True)


def render_team_cards(
    team: list[dict[str, object]],
    *,
    removable: bool = False,
    language: Language = DEFAULT_LANGUAGE,
) -> str | None:
    """Das vollständige Team in einer Reihe darstellen.

    Eine einzelne Karte wird weiterhin zentriert. Sobald mindestens zwei
    Pokémon gewählt sind, teilen sie sich gemeinsam die verfügbare Zeile.
    """
    removed_name: str | None = None

    if len(team) == 1:
        # Eine einzelne Karte soll nicht die komplette Seitenbreite belegen.
        # Leere Randspalten halten sie optisch in der Mitte des Team-Bereichs.
        _, centered_column, _ = st.columns([1, 1, 1])
        columns = [centered_column]
    else:
        columns = st.columns(len(team))

    for column, member in zip(columns, team, strict=True):
        name = str(member["name"])
        type_1 = str(member["type_1"])
        raw_type_2 = member["type_2"]
        type_2 = raw_type_2 if isinstance(raw_type_2, str) else None

        with column.container(border=True):
            sprite_url = member["sprite_url"]
            if isinstance(sprite_url, str):
                st.image(sprite_url, width=112)

            st.subheader(format_name(name))
            st.caption(type_label(type_1, type_2, language=language))
            st.metric(
                text(language, "total_bst"),
                _integer_value(
                    member["base_stat_total"],
                    field="base_stat_total",
                ),
            )

            final_label = text(
                language,
                "final" if bool(member["is_final_evolution"]) else "not_final",
            )
            st.caption(
                text(
                    language,
                    "member_metadata",
                    generation=member["generation"],
                    stage=member["evolution_stage"],
                    max_stage=member["evolution_max_stage"],
                    final_status=final_label,
                )
            )

            if removable and st.button(
                text(language, "remove_from_team"),
                key=f"remove-team-{name}",
                use_container_width=True,
            ):
                removed_name = name

    return removed_name


def render_pokemon_browser(
    candidates: pd.DataFrame,
    *,
    selected_names: list[str],
    language: Language = DEFAULT_LANGUAGE,
) -> tuple[str | None, bool]:
    """Gefilterte Pokémon als kompakte Karten statt als lange Liste anzeigen.

    Zurückgegeben werden der angeklickte Pokémon-Name und die Information, ob
    dieser Name bereits zum Team gehörte. Die eigentliche Zustandsänderung bleibt
    dadurch zentral in ``main``.
    """
    clicked_name: str | None = None
    clicked_was_selected = False
    visible = candidates.head(MAX_VISIBLE_RESULTS)

    for start_index in range(0, len(visible), 4):
        rows = visible.iloc[start_index : start_index + 4]
        columns = st.columns(len(rows))

        for column, (_, pokemon_row) in zip(columns, rows.iterrows(), strict=True):
            name = str(pokemon_row["name"])
            is_selected = name in selected_names
            raw_type_2 = pokemon_row["type_2"]
            type_2 = None if pd.isna(raw_type_2) else str(raw_type_2)

            with column.container(border=True):
                sprite_url = safe_sprite_url(pokemon_row["sprite_url"])
                if sprite_url is not None:
                    st.image(sprite_url, width=96)

                st.markdown(f"**{format_name(name)}**")
                st.caption(
                    f"#{_integer_value(pokemon_row['id'], field='id'):04d} · "
                    f"{type_label(str(pokemon_row['type_1']), type_2, language=language)}"
                )
                st.caption(
                    text(
                        language,
                        "browser_metadata",
                        generation=_integer_value(pokemon_row["generation"], field="generation"),
                        bst=_integer_value(pokemon_row["base_stat_total"], field="base_stat_total"),
                    )
                )

                team_is_full = len(selected_names) >= 5
                button_label = text(
                    language,
                    "remove" if is_selected else "add_to_team",
                )
                if st.button(
                    button_label,
                    key=f"browser-team-{name}",
                    disabled=team_is_full and not is_selected,
                    type="primary" if is_selected else "secondary",
                    use_container_width=True,
                ):
                    clicked_name = name
                    clicked_was_selected = is_selected

    return clicked_name, clicked_was_selected


def render_defense_analysis(
    team: list[dict[str, object]],
    chart: dict[str, dict[str, float]],
    *,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Gemeinsame Schwächen und vollständige Abdeckung sachlich darstellen."""
    analysis = analyze_team_defense(team, chart=chart)
    summary = summarize_team_weaknesses(analysis)
    shared_weaknesses = [entry for entry in summary if entry["weakness_count"] >= 2]

    st.header(text(language, "defense_title"))

    if shared_weaknesses:
        shared_names = ", ".join(
            type_name(language, entry["attacking_type"]) for entry in shared_weaknesses
        )
        st.warning(text(language, "shared_weaknesses", types=shared_names))
    else:
        st.success(text(language, "no_shared_weakness"))

    if summary:
        summary_rows = [
            {
                text(language, "attack_type"): type_name(language, entry["attacking_type"]),
                text(language, "weak_members"): ", ".join(
                    format_name(name) for name in entry["weak_members"]
                ),
                text(language, "weaknesses"): entry["weakness_count"],
                text(language, "resistances"): entry["resistance_count"],
                text(language, "immunities"): entry["immunity_count"],
                text(language, "maximum_factor"): f"×{entry['maximum_multiplier']:g}",
            }
            for entry in summary
        ]
        st.dataframe(
            pd.DataFrame(summary_rows),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander(text(language, "coverage_title")):
        coverage_rows = []

        for attacking_type, entry in analysis.items():
            coverage_rows.append(
                {
                    text(language, "attack_type"): type_name(language, attacking_type),
                    text(language, "weak"): ", ".join(
                        format_name(name) for name in entry["weak_members"]
                    )
                    or "–",
                    text(language, "resistant"): ", ".join(
                        format_name(name) for name in entry["resistant_members"]
                    )
                    or "–",
                    text(language, "immune"): ", ".join(
                        format_name(name) for name in entry["immune_members"]
                    )
                    or "–",
                    text(language, "neutral"): len(entry["neutral_members"]),
                }
            )

        st.dataframe(
            pd.DataFrame(coverage_rows),
            hide_index=True,
            use_container_width=True,
        )


def render_recommendations(
    recommendations: list[Recommendation],
    pokemon: pd.DataFrame,
    *,
    language: Language = DEFAULT_LANGUAGE,
) -> None:
    """Die fünf besten Kandidaten als nachvollziehbare Karten darstellen."""
    if not recommendations:
        st.warning(text(language, "no_recommendations"))
        return

    pokemon_by_id = pokemon.set_index("id", drop=False)
    if not pokemon_by_id.index.is_unique:
        raise ValueError("Pokémon ids must be unique for recommendation rendering.")

    st.header(text(language, "recommendations_title"))
    st.caption(text(language, "recommendations_caption"))

    with st.expander(text(language, "recommendations_explanation_title")):
        st.write(text(language, "recommendations_explanation"))

    for start_index in range(0, len(recommendations), 3):
        recommendation_group = recommendations[start_index : start_index + 3]
        columns = st.columns(len(recommendation_group))

        for rank_offset, (column, recommendation) in enumerate(
            zip(columns, recommendation_group, strict=True),
            start=start_index + 1,
        ):
            pokemon_id = recommendation["pokemon_id"]
            if pokemon_id not in pokemon_by_id.index:
                raise ValueError(f"Unknown recommendation id: {pokemon_id}.")

            row = pokemon_by_id.loc[pokemon_id]
            raw_type_2 = row["type_2"]
            type_2 = None if pd.isna(raw_type_2) else str(raw_type_2)
            presentation = recommendation_presentation(
                recommendation,
                language=language,
            )

            with column.container(border=True):
                sprite_url = safe_sprite_url(row["sprite_url"])
                if sprite_url is not None:
                    st.image(sprite_url, width=112)

                st.subheader(f"{rank_offset}. {format_name(recommendation['name'])}")
                st.caption(type_label(str(row["type_1"]), type_2, language=language))
                st.metric(text(language, "recommendation_score"), presentation["score"])
                st.progress(recommendation["total_score"] / 100.0)
                st.write(presentation["components"])
                st.caption(text(language, "matching_roles", roles=presentation["roles"]))
                if recommendation["covered_threats"]:
                    st.success(
                        text(
                            language,
                            "covered_threats",
                            threats=presentation["threats"],
                        )
                    )
                else:
                    st.caption(presentation["threats"])


def main() -> None:
    """Team-Auswahl, Typenanalyse und Empfehlungen darstellen."""
    st.set_page_config(
        page_title="Pokémon Team Advisor",
        layout="wide",
    )

    title_column, language_column, loadout_column = st.columns([5, 1, 1])
    with language_column:
        language_option = st.segmented_control(
            "Sprache / Language",
            options=LANGUAGE_OPTIONS,
            default="DE",
            key=LANGUAGE_SESSION_KEY,
        )
    language = language_from_option(language_option)

    with title_column:
        st.title("Pokémon Team Advisor")
        st.write(text(language, "intro"))
    with (
        loadout_column,
        st.popover(text(language, "loadouts_open"), use_container_width=True),
    ):
        st.subheader(text(language, "loadouts_title"))
        st.caption(text(language, "loadouts_future"))
        st.write(text(language, "loadouts_description"))
        st.button(
            text(language, "loadout_save"),
            disabled=True,
            use_container_width=True,
        )
        st.button(
            text(language, "loadout_load"),
            disabled=True,
            use_container_width=True,
        )

    try:
        pokemon = load_pokemon_data(POKEMON_DATA_PATH)
        chart = load_type_chart(TYPE_CHART_PATH)
    except (OSError, ValueError):
        # Technische Pfade oder Parserdetails werden bewusst nicht im Browser
        # ausgegeben. Die Oberfläche zeigt nur eine handlungsorientierte Meldung.
        st.error(text(language, "data_error"))
        st.stop()

    # Der Teamzustand enthält ausschließlich Namen, die aus dem validierten
    # Datensatz stammen. Veraltete oder manipulierte Session-Werte werden beim
    # nächsten Seitenlauf verworfen.
    available_names = set(pokemon["name"].astype(str))
    raw_selected_names = st.session_state.get(TEAM_SESSION_KEY, [])
    if not isinstance(raw_selected_names, list):
        raw_selected_names = []

    selected_names: list[str] = []
    for value in raw_selected_names:
        if (
            isinstance(value, str)
            and value in available_names
            and value not in selected_names
            and len(selected_names) < 5
        ):
            selected_names.append(value)
    st.session_state[TEAM_SESSION_KEY] = selected_names

    st.sidebar.header(text(language, "filters_header"))
    selected_types = st.sidebar.multiselect(
        text(language, "filter_type"),
        options=sorted(EXPECTED_TYPES),
        format_func=lambda value: type_name(language, value),
        placeholder=text(language, "all_types"),
    )
    selected_generations = st.sidebar.multiselect(
        text(language, "filter_generation"),
        options=list(range(1, 10)),
        placeholder=text(language, "all_generations"),
    )
    stage_text_keys = {
        "Alle": "stage_all",
        "Basis": "stage_base",
        "1. Entwicklung": "stage_first",
        "2. Entwicklung": "stage_second",
    }
    stage_label = st.sidebar.radio(
        text(language, "filter_stage"),
        options=list(stage_text_keys),
        format_func=lambda value: text(language, stage_text_keys[value]),
    )
    stage_by_label = {
        "Alle": None,
        "Basis": 0,
        "1. Entwicklung": 1,
        "2. Entwicklung": 2,
    }
    final_only = st.sidebar.toggle(text(language, "filter_final_only"))
    dual_type_only = st.sidebar.toggle(text(language, "filter_dual_only"))
    maximum_bst = _integer_value(
        pokemon["base_stat_total"].max(),
        field="maximum_base_stat_total",
    )
    minimum_bst = st.sidebar.slider(
        text(language, "filter_minimum_bst"),
        min_value=0,
        max_value=maximum_bst,
        value=0,
        step=25,
    )
    st.sidebar.divider()
    st.sidebar.caption(
        text(
            language,
            "dataset_summary",
            pokemon_count=len(pokemon),
            type_count=len(chart),
        )
    )

    with st.container(border=True):
        heading_column, metric_column = st.columns([4, 1])
        with heading_column:
            st.subheader(text(language, "team_title"))
            st.caption(text(language, "team_instruction"))
        with metric_column:
            st.metric(text(language, "occupied_slots"), f"{len(selected_names)} / 5")

        free_slots = 5 - len(selected_names)
        st.progress(
            len(selected_names) / 5,
            text=text(
                language,
                "one_free_slot" if free_slots == 1 else "free_slots",
                count=free_slots,
            ),
        )

        if selected_names:
            try:
                team = selected_team_records(pokemon, selected_names)
                removed_name = render_team_cards(
                    team,
                    removable=True,
                    language=language,
                )
            except ValueError:
                st.error(text(language, "team_error"))
                return

            if removed_name is not None:
                st.session_state[TEAM_SESSION_KEY] = [
                    name for name in selected_names if name != removed_name
                ]
                st.rerun()
        else:
            st.info(text(language, "empty_team"))

    if len(selected_names) == 5:
        st.divider()
        try:
            recommender_records = pokemon_recommender_records(pokemon)
            recommender_records_by_name = {
                str(record["name"]): record for record in recommender_records
            }
            team_ids = [
                _integer_value(
                    recommender_records_by_name[name]["id"],
                    field=f"team.{name}.id",
                )
                for name in selected_names
            ]
            recommendations = cached_team_recommendations(
                tuple(team_ids),
                recommender_records,
                chart,
            )
            render_recommendations(
                recommendations,
                pokemon,
                language=language,
            )
        except (KeyError, TypeError, ValueError):
            st.error(text(language, "recommendations_error"))

    st.header(text(language, "search_title"))
    search_column, sort_column = st.columns([3, 1])
    with search_column:
        search_text = live_search_input(
            text(language, "search_label"),
            placeholder=text(language, "search_placeholder"),
            key="pokedex-live-search",
            max_chars=80,
        )
    with sort_column:
        sort_by = st.selectbox(
            text(language, "sort_label"),
            options=list(SORT_OPTIONS),
            format_func=lambda value: text(language, SORT_TEXT_KEYS[value]),
        )

    try:
        candidates = filter_pokemon(
            pokemon,
            search_text=search_text,
            selected_types=selected_types,
            selected_generations=selected_generations,
            evolution_stage=stage_by_label[stage_label],
            final_only=final_only,
            dual_type_only=dual_type_only,
            minimum_base_stat_total=minimum_bst,
            sort_by=sort_by,
        )
    except ValueError:
        st.error(text(language, "filter_error"))
        return

    result_count = len(candidates)
    result_column, limit_column = st.columns(2)
    result_column.metric(text(language, "results"), result_count)
    if result_count > MAX_VISIBLE_RESULTS:
        limit_column.caption(
            text(
                language,
                "results_limited",
                limit=MAX_VISIBLE_RESULTS,
            )
        )

    if candidates.empty:
        st.warning(text(language, "no_results"))
    else:
        clicked_name, clicked_was_selected = render_pokemon_browser(
            candidates,
            selected_names=selected_names,
            language=language,
        )
        if clicked_name is not None:
            if clicked_was_selected:
                updated_names = [name for name in selected_names if name != clicked_name]
            elif len(selected_names) < 5:
                updated_names = [*selected_names, clicked_name]
            else:
                updated_names = selected_names

            st.session_state[TEAM_SESSION_KEY] = updated_names
            st.rerun()

    if selected_names:
        st.divider()
        try:
            render_defense_analysis(
                selected_team_records(pokemon, selected_names),
                chart,
                language=language,
            )
        except ValueError:
            # Keine internen Daten oder Stacktraces an die UI weiterreichen.
            st.error(text(language, "analysis_error"))
            return


if __name__ == "__main__":
    main()
