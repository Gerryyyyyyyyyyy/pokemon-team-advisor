-- Die ursprüngliche Regel setzte "final" fälschlich mit der höchsten Stufe
-- einer gesamten Evolutionsfamilie gleich. Bei verzweigten Familien können
-- einzelne Endzweige früher aufhören: Flapple und Appletun sind beispielsweise
-- auf Stufe 1 final, während der Dipplin-Zweig Stufe 2 erreicht.

BEGIN;

-- Der Name stammt aus der bereits ausgeführten ersten Migration.
ALTER TABLE analytics.pokemon
    DROP CONSTRAINT IF EXISTS pokemon_final_evolution_consistent;

-- Durch IF EXISTS bleibt die Reparatur auch dann wiederholbar, wenn auf einer
-- frischen Datenbank bereits die korrigierte erste Migration verwendet wurde.
ALTER TABLE analytics.pokemon
    DROP CONSTRAINT IF EXISTS pokemon_max_stage_is_final;

-- Pokémon auf der höchsten Stufe müssen final sein. Finale Seitenzweige dürfen
-- jedoch bereits vor der höchsten Stufe der Familie enden.
ALTER TABLE analytics.pokemon
    ADD CONSTRAINT pokemon_max_stage_is_final CHECK (
        evolution_stage < evolution_max_stage OR is_final_evolution
    );

COMMIT;
