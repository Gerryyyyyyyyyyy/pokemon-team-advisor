-- Vergleich von Einzel- und Doppeltypen bei ähnlichem Entwicklungsstand.
--
-- Der unkontrollierte Mittelwert ist potenziell irreführend: Wenn unter den
-- Doppeltypen mehr finale Entwicklungen vorkommen, könnte ihr höherer
-- Gesamtbasiswert durch den Entwicklungsstand statt durch die Typstruktur
-- erklärt werden. Deshalb gruppieren wir zusätzlich nach Stufe und Finalstatus.

SELECT
    evolution_stage,
    is_final_evolution,
    COUNT(*) FILTER (
        WHERE type_2 IS NULL
    ) AS single_type_count,
    COUNT(*) FILTER (
        WHERE type_2 IS NOT NULL
    ) AS dual_type_count,
    ROUND(
        AVG(base_stat_total) FILTER (
            WHERE type_2 IS NULL
        ),
        1
    ) AS single_type_average,
    ROUND(
        AVG(base_stat_total) FILTER (
            WHERE type_2 IS NOT NULL
        ),
        1
    ) AS dual_type_average,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY base_stat_total
        ) FILTER (
            WHERE type_2 IS NULL
        )::NUMERIC,
        1
    ) AS single_type_median,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY base_stat_total
        ) FILTER (
            WHERE type_2 IS NOT NULL
        )::NUMERIC,
        1
    ) AS dual_type_median,
    ROUND(
        AVG(base_stat_total) FILTER (
            WHERE type_2 IS NOT NULL
        )
        - AVG(base_stat_total) FILTER (
            WHERE type_2 IS NULL
        ),
        1
    ) AS adjusted_average_difference
FROM analytics.pokemon
GROUP BY
    evolution_stage,
    is_final_evolution
ORDER BY
    evolution_stage,
    is_final_evolution;
