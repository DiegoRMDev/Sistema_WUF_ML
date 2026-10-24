-- HU04: agrega versionado del árbol de decisión y evaluaciones auditables.
-- Ejecutar una sola vez en la base v4 que ya tiene HU01-HU03.
-- No elimina ni modifica ejecuciones, mascotas, snapshots o modelos anteriores.

BEGIN;

CREATE TABLE IF NOT EXISTS modelo_consistencia (
    id_modelo_consistencia SERIAL PRIMARY KEY,
    version VARCHAR(10) NOT NULL UNIQUE,
    algoritmo VARCHAR(40) NOT NULL DEFAULT 'DecisionTreeClassifier',
    fuente_etiquetas VARCHAR(40) NOT NULL,
    id_ejecucion_referencia INTEGER NOT NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    id_usuario INTEGER NULL REFERENCES usuario (id_usuario),
    fecha_entrenamiento TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accuracy_score DECIMAL(5,4) NOT NULL CHECK (accuracy_score BETWEEN 0 AND 1),
    f1_macro_score DECIMAL(5,4) NOT NULL CHECK (f1_macro_score BETWEEN 0 AND 1),
    nro_registros_entrenamiento INTEGER NOT NULL CHECK (nro_registros_entrenamiento > 0),
    nro_registros_prueba INTEGER NOT NULL CHECK (nro_registros_prueba > 0),
    matriz_confusion JSONB NOT NULL,
    importancia_variables JSONB NOT NULL,
    reglas_arbol TEXT NOT NULL,
    metadatos_entrenamiento JSONB NOT NULL,
    artefacto_ruta VARCHAR(255) NOT NULL,
    artefacto_sha256 CHAR(64) NOT NULL CHECK (artefacto_sha256 ~ '^[0-9a-f]{64}$'),
    es_vigente BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_modelo_consistencia_fuente CHECK (fuente_etiquetas IN ('reglas_demo_hu04_v1', 'prioridad_revision_hu04_v2')),
    CONSTRAINT ck_modelo_consistencia_algoritmo CHECK (algoritmo = 'DecisionTreeClassifier')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_modelo_consistencia_vigente
    ON modelo_consistencia (es_vigente) WHERE es_vigente;

CREATE TABLE IF NOT EXISTS evaluacion_consistencia (
    id_evaluacion SERIAL PRIMARY KEY,
    id_modelo_consistencia INTEGER NOT NULL
        REFERENCES modelo_consistencia (id_modelo_consistencia) ON DELETE CASCADE,
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    id_snapshot INTEGER NOT NULL REFERENCES snapshot_catalogo (id_snapshot),
    id_ejecucion INTEGER NOT NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    fecha_evaluacion DATE NOT NULL,
    nivel_riesgo VARCHAR(10) NOT NULL,
    fuente_etiqueta VARCHAR(40) NOT NULL,
    justificacion VARCHAR(500) NOT NULL,
    indicadores JSONB NOT NULL,
    CONSTRAINT ck_evaluacion_consistencia_riesgo CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto')),
    CONSTRAINT ck_evaluacion_consistencia_fuente CHECK (fuente_etiqueta IN ('reglas_demo_hu04_v1', 'prioridad_revision_hu04_v2')),
    CONSTRAINT fk_evaluacion_consistencia_snapshot_mascota
        FOREIGN KEY (id_ejecucion, id_mascota)
        REFERENCES snapshot_catalogo (id_ejecucion, id_mascota),
    CONSTRAINT uq_evaluacion_consistencia_modelo_mascota
        UNIQUE (id_modelo_consistencia, id_ejecucion, id_mascota)
);
CREATE INDEX IF NOT EXISTS ix_evaluacion_consistencia_ejecucion_riesgo
    ON evaluacion_consistencia (id_ejecucion, nivel_riesgo);

COMMIT;
