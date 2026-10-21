-- WUF Predict v2: esquema completo para HU01/HU02/HU03 sobre PostgreSQL 16.
-- Ejecutar SOLO conectado a una base vacía (wuf_predict_v2, wuf_predict_v3 o wuf_predict_v4).
-- No crea ni elimina bases; conserva backend/schema.sql para la instalación anterior.
-- Incluye desde el inicio las columnas, restricciones e índices de HU03.
-- upgrade_hu03_ml.sql es para esquemas v2/v3 anteriores; sobre este esquema completo es redundante.
-- HU01 recibirá la fecha de captura del CSV, mientras fecha_inicio/fecha_fin
-- auditan el momento real de importación. La semana se calcula en la aplicación
-- mediante calendario ISO y se verifica aquí contra la fecha de captura.

BEGIN;

CREATE TABLE usuario (
    id_usuario SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    rol VARCHAR(20) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    CONSTRAINT ck_usuario_rol CHECK (rol IN ('analista', 'marketing', 'ayuda'))
);

CREATE TABLE mascota (
    id_mascota SERIAL PRIMARY KEY,
    sku VARCHAR(10) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL,
    especie VARCHAR(10) NOT NULL,
    raza VARCHAR(30) NOT NULL,
    sexo CHAR(1) NOT NULL,
    edad_meses INTEGER NULL,
    edad_estimada BOOLEAN NOT NULL,
    tipo_pelaje VARCHAR(15) NOT NULL,
    tamano VARCHAR(10) NOT NULL,
    tamano_estimado BOOLEAN NOT NULL,
    nivel_energia VARCHAR(10) NOT NULL,
    condicion_especial BOOLEAN NOT NULL,
    condicion_detalle VARCHAR(200) NULL,
    descripcion VARCHAR(512) NULL,
    orden_publicacion INTEGER NOT NULL,
    estado_publicado VARCHAR(20) NOT NULL,
    fecha_publicacion DATE NOT NULL,
    url_perfil VARCHAR(255) NOT NULL,
    CONSTRAINT ck_mascota_edad_meses_no_negativa CHECK (edad_meses IS NULL OR edad_meses >= 0),
    CONSTRAINT ck_mascota_orden_publicacion_positivo CHECK (orden_publicacion > 0)
);

CREATE TABLE etiqueta_condicion (
    id_etiqueta SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    etiqueta VARCHAR(30) NOT NULL,
    CONSTRAINT uq_etiqueta_condicion_mascota UNIQUE (id_mascota, etiqueta)
);

CREATE TABLE adoptante (
    id_adoptante SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL
);

CREATE TABLE adopcion (
    id_adopcion SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    id_adoptante INTEGER NOT NULL REFERENCES adoptante (id_adoptante),
    fecha_adopcion DATE NOT NULL,
    costo DECIMAL(8,2) NOT NULL,
    estado VARCHAR(20) NOT NULL,
    CONSTRAINT ck_adopcion_costo_no_negativo CHECK (costo >= 0)
);

CREATE TABLE dataset_historico (
    id_dataset SERIAL PRIMARY KEY,
    fecha_generacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nro_registros INTEGER NOT NULL DEFAULT 0,
    version VARCHAR(20) NOT NULL,
    origen_etiquetas VARCHAR(24) NOT NULL,
    fecha_desde DATE NOT NULL,
    fecha_hasta DATE NOT NULL,
    version_regla_etiquetado VARCHAR(30) NOT NULL,
    hash_sha256 CHAR(64) NULL,
    CONSTRAINT ck_dataset_nro_registros_no_negativo CHECK (nro_registros >= 0),
    CONSTRAINT ck_dataset_origen_etiquetas CHECK (
        origen_etiquetas IN ('derivada_catalogo', 'sintetica', 'verificada', 'mixta', 'desconocida')
    ),
    CONSTRAINT ck_dataset_rango_fechas CHECK (fecha_hasta >= fecha_desde),
    CONSTRAINT ck_dataset_hash_sha256 CHECK (hash_sha256 IS NULL OR hash_sha256 ~ '^[0-9a-fA-F]{64}$')
);

CREATE TABLE ejecucion_recoleccion (
    id_ejecucion SERIAL PRIMARY KEY,
    id_usuario INTEGER NULL REFERENCES usuario (id_usuario),
    tipo_ejecucion VARCHAR(15) NOT NULL DEFAULT 'manual',
    fuente_datos VARCHAR(24) NOT NULL DEFAULT 'csv_simulada',
    referencia_fuente VARCHAR(255) NULL,
    fecha_captura DATE NOT NULL,
    semana SMALLINT NOT NULL,
    fecha_inicio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP NULL,
    perfiles_total INTEGER NOT NULL DEFAULT 0,
    perfiles_disponibles INTEGER NOT NULL DEFAULT 0,
    perfiles_no_disponibles INTEGER NOT NULL DEFAULT 0,
    perfiles_sin_publicar INTEGER NOT NULL DEFAULT 0,
    estado VARCHAR(15) NOT NULL,
    mensaje_error VARCHAR(1000) NULL,
    CONSTRAINT ck_ejecucion_tipo CHECK (tipo_ejecucion IN ('manual', 'programada')),
    CONSTRAINT ck_ejecucion_fuente CHECK (fuente_datos = 'csv_simulada'),
    CONSTRAINT ck_ejecucion_semana CHECK (
        semana BETWEEN 1 AND 53 AND semana = EXTRACT(WEEK FROM fecha_captura)::SMALLINT
    ),
    CONSTRAINT ck_ejecucion_conteos CHECK (
        perfiles_total >= 0 AND perfiles_disponibles >= 0
        AND perfiles_no_disponibles >= 0 AND perfiles_sin_publicar >= 0
    ),
    CONSTRAINT ck_ejecucion_estado CHECK (estado IN ('en_proceso', 'completada', 'parcial', 'fallida')),
    CONSTRAINT ck_ejecucion_fechas CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE INDEX ix_ejecucion_recoleccion_fecha_captura
    ON ejecucion_recoleccion (fecha_captura DESC, id_ejecucion DESC);
CREATE UNIQUE INDEX uq_ejecucion_csv_referencia
    ON ejecucion_recoleccion (fuente_datos, referencia_fuente)
    WHERE fuente_datos = 'csv_simulada' AND referencia_fuente IS NOT NULL
      AND estado IN ('en_proceso', 'completada', 'parcial');

CREATE TABLE snapshot_catalogo (
    id_snapshot SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    id_ejecucion INTEGER NOT NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    semana SMALLINT NOT NULL,
    fecha_captura TIMESTAMP NOT NULL,
    sku VARCHAR(10) NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    especie VARCHAR(10) NOT NULL,
    raza VARCHAR(30) NOT NULL,
    sexo CHAR(1) NOT NULL,
    edad_meses INTEGER NULL,
    edad_estimada BOOLEAN NOT NULL,
    tipo_pelaje VARCHAR(15) NOT NULL,
    tamano VARCHAR(10) NOT NULL,
    tamano_estimado BOOLEAN NOT NULL,
    nivel_energia VARCHAR(10) NOT NULL,
    condicion_especial BOOLEAN NOT NULL,
    condicion_detalle VARCHAR(200) NULL,
    descripcion VARCHAR(512) NULL,
    orden_publicacion INTEGER NOT NULL,
    estado_detectado VARCHAR(20) NOT NULL,
    fecha_publicacion DATE NOT NULL,
    url_perfil VARCHAR(255) NOT NULL,
    -- Campo heredado del diseño académico; HU02 no lo usa como etiqueta derivada.
    etiqueta_adoptado BOOLEAN NULL,
    origen_etiqueta VARCHAR(20) NULL,
    CONSTRAINT ck_snapshot_semana CHECK (
        semana BETWEEN 1 AND 53 AND semana = EXTRACT(WEEK FROM fecha_captura)::SMALLINT
    ),
    CONSTRAINT ck_snapshot_edad CHECK (edad_meses IS NULL OR edad_meses >= 0),
    CONSTRAINT ck_snapshot_orden CHECK (orden_publicacion > 0),
    CONSTRAINT ck_snapshot_origen_etiqueta CHECK (
        (etiqueta_adoptado IS NULL AND origen_etiqueta IS NULL)
        OR (etiqueta_adoptado IS NOT NULL AND origen_etiqueta IS NOT NULL
            AND origen_etiqueta IN ('sintetica', 'verificada', 'inferida', 'desconocida'))
    ),
    CONSTRAINT uq_snapshot_ejecucion_mascota UNIQUE (id_ejecucion, id_mascota)
);

CREATE INDEX ix_snapshot_mascota_fecha
    ON snapshot_catalogo (id_mascota, fecha_captura DESC);
CREATE INDEX ix_snapshot_semana_sku
    ON snapshot_catalogo (semana, sku);

CREATE TABLE snapshot_etiqueta_condicion (
    id_snapshot INTEGER NOT NULL REFERENCES snapshot_catalogo (id_snapshot),
    etiqueta VARCHAR(30) NOT NULL,
    PRIMARY KEY (id_snapshot, etiqueta)
);

-- Un dataset puede reutilizar snapshots y cada snapshot puede participar
-- en varias versiones de dataset: relación muchos-a-muchos explícita.
CREATE TABLE dataset_snapshot (
    id_dataset INTEGER NOT NULL REFERENCES dataset_historico (id_dataset) ON DELETE CASCADE,
    id_snapshot INTEGER NOT NULL REFERENCES snapshot_catalogo (id_snapshot),
    PRIMARY KEY (id_dataset, id_snapshot)
);

-- Una fila representa una mascota en el dataset y el resultado de comparar
-- un snapshot de referencia con el siguiente snapshot observado.
-- Registra todas las ejecuciones consideradas, incluidas las capturas completas
-- donde una mascota estuvo ausente y esa ausencia sirvió como evidencia.
CREATE TABLE dataset_ejecucion (
    id_dataset INTEGER NOT NULL REFERENCES dataset_historico (id_dataset) ON DELETE CASCADE,
    id_ejecucion INTEGER NOT NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    PRIMARY KEY (id_dataset, id_ejecucion)
);

CREATE TABLE dataset_detalle (
    id_dataset_detalle SERIAL PRIMARY KEY,
    id_dataset INTEGER NOT NULL REFERENCES dataset_historico (id_dataset) ON DELETE CASCADE,
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    id_snapshot_referencia INTEGER NOT NULL REFERENCES snapshot_catalogo (id_snapshot),
    id_ejecucion_resultado INTEGER NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    id_snapshot_resultado INTEGER NULL REFERENCES snapshot_catalogo (id_snapshot),
    etiqueta_catalogo VARCHAR(24) NOT NULL,
    interpretacion_rf03 VARCHAR(20) NOT NULL DEFAULT 'proxy',
    motivo_indeterminado VARCHAR(255) NULL,
    CONSTRAINT ck_dataset_detalle_etiqueta CHECK (
        etiqueta_catalogo IN ('permanece', 'salio_catalogo', 'indeterminada')
    ),
    CONSTRAINT ck_dataset_detalle_interpretacion CHECK (
        interpretacion_rf03 IN ('proxy', 'verificada', 'no_aplica')
    ),
    CONSTRAINT ck_dataset_detalle_evidencia CHECK (
        (etiqueta_catalogo = 'permanece'
            AND id_ejecucion_resultado IS NOT NULL AND id_snapshot_resultado IS NOT NULL)
        OR (etiqueta_catalogo = 'salio_catalogo' AND id_ejecucion_resultado IS NOT NULL)
        OR etiqueta_catalogo = 'indeterminada'
    ),
    CONSTRAINT fk_dataset_detalle_snapshot_referencia
        FOREIGN KEY (id_dataset, id_snapshot_referencia)
        REFERENCES dataset_snapshot (id_dataset, id_snapshot),
    CONSTRAINT fk_dataset_detalle_snapshot_resultado
        FOREIGN KEY (id_dataset, id_snapshot_resultado)
        REFERENCES dataset_snapshot (id_dataset, id_snapshot),
    CONSTRAINT fk_dataset_detalle_ejecucion_resultado
        FOREIGN KEY (id_dataset, id_ejecucion_resultado)
        REFERENCES dataset_ejecucion (id_dataset, id_ejecucion),
    CONSTRAINT uq_dataset_detalle_mascota UNIQUE (id_dataset, id_mascota)
);

CREATE TABLE modelo_predictivo (
    id_modelo SERIAL PRIMARY KEY,
    id_dataset INTEGER NOT NULL REFERENCES dataset_historico (id_dataset),
    algoritmo VARCHAR(30) NOT NULL,
    version VARCHAR(10) NOT NULL,
    accuracy_score DECIMAL(5,4) NOT NULL,
    precision_score DECIMAL(5,4) NOT NULL,
    recall_score DECIMAL(5,4) NOT NULL,
    f1_score DECIMAL(5,4) NOT NULL,
    fecha_entrenamiento TIMESTAMP NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'no_publicable',
    metadatos_entrenamiento JSONB NOT NULL DEFAULT '{}'::jsonb,
    clase_positiva VARCHAR(30) NOT NULL DEFAULT 'salio_catalogo',
    nro_registros_entrenamiento INTEGER NOT NULL DEFAULT 0,
    nro_registros_prueba INTEGER NOT NULL DEFAULT 0,
    nro_registros_excluidos INTEGER NOT NULL DEFAULT 0,
    umbral_accuracy DECIMAL(5,4) NOT NULL DEFAULT 0.7500,
    matriz_confusion JSONB NOT NULL DEFAULT '[]'::jsonb,
    importancia_variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    artefacto_ruta VARCHAR(255),
    artefacto_sha256 VARCHAR(64),
    es_vigente BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_modelo_metricas CHECK (
        accuracy_score BETWEEN 0 AND 1 AND precision_score BETWEEN 0 AND 1
        AND recall_score BETWEEN 0 AND 1 AND f1_score BETWEEN 0 AND 1
    ),
    CONSTRAINT ck_modelo_estado CHECK (estado IN ('no_publicable', 'publicable', 'publicado', 'vigente')),
    CONSTRAINT ck_modelo_conteos CHECK (
        nro_registros_entrenamiento >= 0 AND nro_registros_prueba >= 0
        AND nro_registros_excluidos >= 0 AND umbral_accuracy BETWEEN 0 AND 1
    ),
    CONSTRAINT ck_modelo_sha256 CHECK (artefacto_sha256 IS NULL OR artefacto_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE UNIQUE INDEX uq_modelo_predictivo_vigente
    ON modelo_predictivo (es_vigente) WHERE es_vigente = TRUE;

CREATE TABLE reporte_priorizacion (
    id_reporte SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuario (id_usuario),
    semana INTEGER NOT NULL CHECK (semana BETWEEN 1 AND 53),
    fecha_generacion TIMESTAMP NOT NULL,
    formato VARCHAR(10) NOT NULL
);

CREATE TABLE prediccion (
    id_prediccion SERIAL PRIMARY KEY,
    id_modelo INTEGER NOT NULL REFERENCES modelo_predictivo (id_modelo),
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    id_ejecucion INTEGER NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    id_reporte INTEGER NULL REFERENCES reporte_priorizacion (id_reporte),
    probabilidad_adopcion DECIMAL(5,4) NOT NULL CHECK (probabilidad_adopcion BETWEEN 0 AND 1),
    nivel_prioridad VARCHAR(10) NOT NULL,
    fecha TIMESTAMP NOT NULL
);

CREATE TABLE alerta_desactualizacion (
    id_alerta SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL REFERENCES mascota (id_mascota),
    fecha TIMESTAMP NOT NULL,
    nivel_riesgo VARCHAR(10) NOT NULL,
    mensaje VARCHAR(255) NOT NULL,
    estado VARCHAR(15) NOT NULL
);

COMMIT;
