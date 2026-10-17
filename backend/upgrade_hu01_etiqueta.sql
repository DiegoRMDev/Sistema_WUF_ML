-- Permite que HU01 guarde snapshots sin afirmar una adopción que la fuente no confirma.
-- Ejecutar una sola vez en PostgreSQL 16 después de upgrade_hu01.sql.
BEGIN;

ALTER TABLE snapshot_catalogo
    ALTER COLUMN etiqueta_adoptado DROP NOT NULL;

COMMIT;
