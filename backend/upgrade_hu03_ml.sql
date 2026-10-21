-- Migración para esquemas v2/v3 anteriores que aún no incluyen las estructuras HU03.
-- No es necesaria para una base nueva creada desde schema_wuf_predict_v4.sql.
BEGIN;

ALTER TABLE modelo_predictivo
    ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'no_publicable',
    ADD COLUMN IF NOT EXISTS metadatos_entrenamiento JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS clase_positiva VARCHAR(30) NOT NULL DEFAULT 'salio_catalogo',
    ADD COLUMN IF NOT EXISTS nro_registros_entrenamiento INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS nro_registros_prueba INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS nro_registros_excluidos INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS umbral_accuracy DECIMAL(5,4) NOT NULL DEFAULT 0.7500,
    ADD COLUMN IF NOT EXISTS matriz_confusion JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS importancia_variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS artefacto_ruta VARCHAR(255),
    ADD COLUMN IF NOT EXISTS artefacto_sha256 VARCHAR(64),
    ADD COLUMN IF NOT EXISTS es_vigente BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE prediccion
    ADD COLUMN IF NOT EXISTS id_ejecucion INTEGER NULL REFERENCES ejecucion_recoleccion (id_ejecucion);

DO $$ BEGIN
    ALTER TABLE modelo_predictivo ADD CONSTRAINT ck_modelo_estado
        CHECK (estado IN ('no_publicable', 'publicable', 'publicado', 'vigente'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE modelo_predictivo ADD CONSTRAINT ck_modelo_conteos
        CHECK (nro_registros_entrenamiento >= 0 AND nro_registros_prueba >= 0
               AND nro_registros_excluidos >= 0 AND umbral_accuracy BETWEEN 0 AND 1);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE modelo_predictivo ADD CONSTRAINT ck_modelo_sha256
        CHECK (artefacto_sha256 IS NULL OR artefacto_sha256 ~ '^[0-9a-f]{64}$');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_modelo_predictivo_vigente
    ON modelo_predictivo (es_vigente) WHERE es_vigente = TRUE;

COMMIT;
