-- Häufigkeit und Werteprofile aller Pokémon-Typen.
--
-- Ein Typ kann in type_1 oder type_2 stehen. CROSS JOIN LATERAL wandelt beide
-- Spalten in Zeilen um, damit jeder Typ mit derselben Logik ausgewertet wird.
-- Weil die Tabelle gleiche Primär- und Sekundärtypen verbietet, wird ein Pokémon
-- innerhalb eines Typs nicht doppelt gezählt.

WITH type_memberships AS (
    SELECT
        pokemon.id,
        pokemon.base_stat_total,
        pokemon.attack,
        pokemon.special_attack,
        pokemon.defense,
        pokemon.special_defense,
        pokemon.speed,
        pokemon.is_final_evolution,
        type_slot.slot_number,
        type_slot.type_name
    FROM analytics.pokemon AS pokemon
    CROSS JOIN LATERAL (
        VALUES
            (1, pokemon.type_1),
            (2, pokemon.type_2)
    ) AS type_slot (slot_number, type_name)
    WHERE type_slot.type_name IS NOT NULL
),
type_summary AS (
    SELECT
        type_name,
        COUNT(*) AS pokemon_count,
        COUNT(*) FILTER (
            WHERE slot_number = 1
        ) AS primary_type_count,
        COUNT(*) FILTER (
            WHERE slot_number = 2
        ) AS secondary_type_count,
        ROUND(AVG(base_stat_total), 1) AS average_base_stat_total,
        ROUND(AVG(attack), 1) AS average_attack,
        ROUND(AVG(special_attack), 1) AS average_special_attack,
        ROUND(AVG(defense), 1) AS average_defense,
        ROUND(AVG(special_defense), 1) AS average_special_defense,
        ROUND(AVG(speed), 1) AS average_speed,
        ROUND(
            100.0 * COUNT(*) FILTER (
                WHERE is_final_evolution
            ) / COUNT(*),
            1
        ) AS final_evolution_percentage
    FROM type_memberships
    GROUP BY type_name
)
SELECT
    RANK() OVER (
        ORDER BY pokemon_count DESC
    ) AS frequency_rank,
    type_name,
    pokemon_count,
    primary_type_count,
    secondary_type_count,
    average_base_stat_total,
    average_attack,
    average_special_attack,
    average_defense,
    average_special_defense,
    average_speed,
    final_evolution_percentage
FROM type_summary
ORDER BY
    pokemon_count DESC,
    type_name;
