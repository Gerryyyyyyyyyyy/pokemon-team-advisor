-- Veränderung des Gesamtbasiswerts entlang der Evolutionsstufen.
--
-- Verzweigte Familien können auf einer Stufe mehrere Pokémon besitzen. Deshalb
-- wird zuerst pro Evolutionsfamilie und Stufe ein Mittelwert gebildet. So erhält
-- beispielsweise die stark verzweigte Eevee-Familie nicht automatisch mehr
-- Gewicht als eine lineare Evolutionsfamilie.

WITH family_stage AS (
    SELECT
        evolution_family,
        evolution_stage,
        COUNT(*) AS species_count,
        AVG(base_stat_total) AS family_stage_average
    FROM analytics.pokemon
    GROUP BY
        evolution_family,
        evolution_stage
),
stage_progression AS (
    SELECT
        evolution_family,
        evolution_stage,
        species_count,
        family_stage_average,
        family_stage_average - LAG(family_stage_average) OVER (
            PARTITION BY evolution_family
            ORDER BY evolution_stage
        ) AS gain_from_previous_stage
    FROM family_stage
)
SELECT
    evolution_stage,
    COUNT(*) AS represented_families,
    SUM(species_count) AS pokemon_count,
    ROUND(AVG(family_stage_average), 1) AS average_family_stage_total,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY family_stage_average
        )::NUMERIC,
        1
    ) AS median_family_stage_total,
    ROUND(AVG(gain_from_previous_stage), 1) AS average_gain_from_previous_stage,
    ROUND(MIN(gain_from_previous_stage), 1) AS minimum_gain_from_previous_stage,
    ROUND(MAX(gain_from_previous_stage), 1) AS maximum_gain_from_previous_stage
FROM stage_progression
GROUP BY evolution_stage
ORDER BY evolution_stage;
