-- Actualiza una base v4 que ya tiene HU04 para aceptar la regla versionada v2.
-- Conserva los registros HU04 y permite consultar versiones históricas de la regla v1.
BEGIN;

ALTER TABLE modelo_consistencia
    DROP CONSTRAINT IF EXISTS ck_modelo_consistencia_fuente;
ALTER TABLE modelo_consistencia
    ADD CONSTRAINT ck_modelo_consistencia_fuente
    CHECK (fuente_etiquetas IN ('reglas_demo_hu04_v1', 'prioridad_revision_hu04_v2'));

ALTER TABLE evaluacion_consistencia
    DROP CONSTRAINT IF EXISTS ck_evaluacion_consistencia_fuente;
ALTER TABLE evaluacion_consistencia
    ADD CONSTRAINT ck_evaluacion_consistencia_fuente
    CHECK (fuente_etiqueta IN ('reglas_demo_hu04_v1', 'prioridad_revision_hu04_v2'));

COMMIT;
