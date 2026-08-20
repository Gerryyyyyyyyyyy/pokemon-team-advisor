-- Reproduzierbare Qualitäts- und Sicherheitsprüfungen für den SQL-Datensatz.
-- Jede Zeile beschreibt eine Erwartung, ihren beobachteten Wert und ob sie gilt.

WITH type_memberships AS (
    SELECT type_1 AS type_name
    FROM analytics.pokemon

    UNION ALL

    SELECT type_2 AS type_name
    FROM analytics.pokemon
    WHERE type_2 IS NOT NULL
),
quality_checks AS (
    SELECT
        'row_count' AS check_name,
        COUNT(*) = 1025 AS passed,
        COUNT(*)::TEXT AS observed_value,
        '1025' AS expected_value
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'unique_ids',
        COUNT(DISTINCT id) = COUNT(*),
        COUNT(DISTINCT id)::TEXT,
        COUNT(*)::TEXT
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'unique_names',
        COUNT(DISTINCT name) = COUNT(*),
        COUNT(DISTINCT name)::TEXT,
        COUNT(*)::TEXT
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'unique_species',
        COUNT(DISTINCT species_name) = COUNT(*),
        COUNT(DISTINCT species_name)::TEXT,
        COUNT(*)::TEXT
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'dual_type_count',
        COUNT(*) FILTER (WHERE type_2 IS NOT NULL) = 526,
        COUNT(*) FILTER (WHERE type_2 IS NOT NULL)::TEXT,
        '526'
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'type_membership_count',
        COUNT(*) = 1551,
        COUNT(*)::TEXT,
        '1551'
    FROM type_memberships

    UNION ALL

    SELECT
        'distinct_type_count',
        COUNT(DISTINCT type_name) = 18,
        COUNT(DISTINCT type_name)::TEXT,
        '18'
    FROM type_memberships

    UNION ALL

    SELECT
        'correct_base_stat_totals',
        COUNT(*) FILTER (
            WHERE base_stat_total <>
                hp + attack + defense
                + special_attack + special_defense + speed
        ) = 0,
        COUNT(*) FILTER (
            WHERE base_stat_total <>
                hp + attack + defense
                + special_attack + special_defense + speed
        )::TEXT,
        '0'
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'valid_evolution_stage_order',
        COUNT(*) FILTER (
            WHERE evolution_stage > evolution_max_stage
        ) = 0,
        COUNT(*) FILTER (
            WHERE evolution_stage > evolution_max_stage
        )::TEXT,
        '0'
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'maximum_stage_is_final',
        COUNT(*) FILTER (
            WHERE evolution_stage = evolution_max_stage
              AND NOT is_final_evolution
        ) = 0,
        COUNT(*) FILTER (
            WHERE evolution_stage = evolution_max_stage
              AND NOT is_final_evolution
        )::TEXT,
        '0'
    FROM analytics.pokemon

    UNION ALL

    SELECT
        'rls_enabled',
        relrowsecurity,
        relrowsecurity::TEXT,
        'true'
    FROM pg_class
    WHERE oid = 'analytics.pokemon'::REGCLASS
)
SELECT
    check_name,
    passed,
    observed_value,
    expected_value
FROM quality_checks
ORDER BY check_name;
