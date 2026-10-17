-- HU01: registra la fuente de datos usada en cada ejecución.
-- Ejecutar una sola vez en la base wuf_predict después de las migraciones HU01 previas.
-- Las ejecuciones existentes se conservan y se marcan con su origen original WUF.

BEGIN;

ALTER TABLE ejecucion_recoleccion
    ADD COLUMN fuente_datos VARCHAR(24) NOT NULL DEFAULT 'wuf',
    ADD CONSTRAINT ck_ejecucion_fuente_datos
        CHECK (fuente_datos IN ('wuf', 'base_local_simulada'));

COMMIT;
