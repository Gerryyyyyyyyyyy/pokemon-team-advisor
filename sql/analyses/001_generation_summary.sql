-- Pokémon-Anzahl und Basiswertverteilung nach Einführungsgeneration.
--
-- Diese Analyse beantwortet unter anderem:
--   * Wie groß ist jede Generation im Datensatz?
--   * Wie unterscheiden sich mittlerer und medianer Gesamtbasiswert?
--   * Wie häufig kommen Doppeltypen und finale Entwicklungen vor?

WITH generation_summary AS (
    SELECT
        generation,
        COUNT(*) AS pokemon_count,
        ROUND(AVG(base_stat_total), 1) AS average_base_stat_total,
        ROUND(
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY base_stat_total
            )::NUMERIC,
            1
        ) AS median_base_stat_total,
        MIN(base_stat_total) AS minimum_base_stat_total,
        MAX(base_stat_total) AS maximum_base_stat_total,
        COUNT(*) FILTER (
            WHERE type_2 IS NOT NULL
        ) AS dual_type_count,
        COUNT(*) FILTER (
            WHERE is_final_evolution
        ) AS final_evolution_count
    FROM analytics.pokemon
    GROUP BY generation
)
SELECT
    generation,
    pokemon_count,
    average_base_stat_total,
    median_base_stat_total,
    minimum_base_stat_total,
    maximum_base_stat_total,
    dual_type_count,
    ROUND(
        100.0 * dual_type_count / pokemon_count,
        1
    ) AS dual_type_percentage,
    final_evolution_count,
    ROUND(
        100.0 * final_evolution_count / pokemon_count,
        1
    ) AS final_evolution_percentage
FROM generation_summary
ORDER BY generation;
