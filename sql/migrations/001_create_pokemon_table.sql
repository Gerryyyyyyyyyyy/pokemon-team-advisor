-- Erste PostgreSQL-Migration für den aufbereiteten Pokémon-Datensatz.
--
-- Das eigene Schema trennt Analysedaten von Supabases standardmäßig
-- API-exponiertem public-Schema. Die Anwendung greift ausschließlich über die
-- direkte, serverseitige PostgreSQL-Verbindung darauf zu.

BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;

-- Rollen erhalten nicht automatisch Zugriff auf das Analyseschema. Der Besitzer
-- der Datenbank darf weiterhin Migrationen, Importe und Analysen ausführen.
REVOKE ALL ON SCHEMA analytics FROM PUBLIC;

CREATE TABLE IF NOT EXISTS analytics.pokemon (
    -- PokéAPI-ID und Namen identifizieren eine Standardform eindeutig.
    id INTEGER PRIMARY KEY CHECK (id > 0),
    name TEXT NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    species_name TEXT NOT NULL UNIQUE CHECK (btrim(species_name) <> ''),
    is_default BOOLEAN NOT NULL CHECK (is_default),

    -- Der erste Typ ist verpflichtend, der zweite Typ optional.
    type_1 TEXT NOT NULL,
    type_2 TEXT,

    -- Basiswerte liegen bei den aktuellen Standardformen zwischen 1 und 255.
    hp SMALLINT NOT NULL CHECK (hp BETWEEN 1 AND 255),
    attack SMALLINT NOT NULL CHECK (attack BETWEEN 1 AND 255),
    defense SMALLINT NOT NULL CHECK (defense BETWEEN 1 AND 255),
    special_attack SMALLINT NOT NULL CHECK (special_attack BETWEEN 1 AND 255),
    special_defense SMALLINT NOT NULL CHECK (special_defense BETWEEN 1 AND 255),
    speed SMALLINT NOT NULL CHECK (speed BETWEEN 1 AND 255),
    base_stat_total SMALLINT NOT NULL CHECK (base_stat_total > 0),

    -- Es werden nur die bereits geprüften HTTPS-Sprites aus dem PokéAPI-
    -- Repository gespeichert.
    sprite_url TEXT NOT NULL CHECK (
        sprite_url LIKE 'https://raw.githubusercontent.com/PokeAPI/sprites/%'
    ),

    -- Generation bezeichnet die Einführung des Pokémon, nicht den aktuell
    -- ausgewählten Kampfregelstand.
    generation SMALLINT NOT NULL CHECK (generation BETWEEN 1 AND 9),

    -- evolution_family ist für Analysen verlässlicher als chain_id: PokéAPI hat
    -- beispielsweise bei Meltan und Melmetal unterschiedliche Chain-IDs, obwohl
    -- beide fachlich zu derselben Evolutionsfamilie gehören.
    evolution_chain_id INTEGER NOT NULL CHECK (evolution_chain_id > 0),
    evolution_family TEXT NOT NULL CHECK (btrim(evolution_family) <> ''),
    evolution_stage SMALLINT NOT NULL CHECK (evolution_stage BETWEEN 0 AND 2),
    evolution_max_stage SMALLINT NOT NULL CHECK (
        evolution_max_stage BETWEEN 0 AND 2
    ),
    is_final_evolution BOOLEAN NOT NULL,

    -- Der Zeitpunkt hilft später nachzuvollziehen, wann ein Datensatz zuletzt
    -- aus der aufbereiteten CSV in PostgreSQL geladen wurde.
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pokemon_type_1_valid CHECK (
        type_1 IN (
            'bug', 'dark', 'dragon', 'electric', 'fairy', 'fighting',
            'fire', 'flying', 'ghost', 'grass', 'ground', 'ice',
            'normal', 'poison', 'psychic', 'rock', 'steel', 'water'
        )
    ),
    CONSTRAINT pokemon_type_2_valid CHECK (
        type_2 IS NULL OR type_2 IN (
            'bug', 'dark', 'dragon', 'electric', 'fairy', 'fighting',
            'fire', 'flying', 'ghost', 'grass', 'ground', 'ice',
            'normal', 'poison', 'psychic', 'rock', 'steel', 'water'
        )
    ),
    CONSTRAINT pokemon_types_distinct CHECK (
        type_2 IS NULL OR type_1 <> type_2
    ),
    CONSTRAINT pokemon_base_stat_total_correct CHECK (
        base_stat_total = hp + attack + defense
            + special_attack + special_defense + speed
    ),
    CONSTRAINT pokemon_evolution_stage_order_valid CHECK (
        evolution_stage <= evolution_max_stage
    ),
    CONSTRAINT pokemon_final_evolution_consistent CHECK (
        is_final_evolution = (evolution_stage = evolution_max_stage)
    )
);

-- Auch bei einer später geänderten Standardsicherheitskonfiguration soll die
-- Tabelle nicht automatisch für alle Datenbankrollen lesbar sein.
REVOKE ALL ON TABLE analytics.pokemon FROM PUBLIC;

-- Diese Indizes unterstützen die geplanten Gruppierungen und Filter. Der
-- Primärschlüssel und die UNIQUE-Spalten besitzen bereits eigene Indizes.
CREATE INDEX IF NOT EXISTS pokemon_generation_idx
    ON analytics.pokemon (generation);

CREATE INDEX IF NOT EXISTS pokemon_type_1_idx
    ON analytics.pokemon (type_1);

CREATE INDEX IF NOT EXISTS pokemon_type_2_idx
    ON analytics.pokemon (type_2)
    WHERE type_2 IS NOT NULL;

CREATE INDEX IF NOT EXISTS pokemon_evolution_family_idx
    ON analytics.pokemon (evolution_family);

COMMIT;
