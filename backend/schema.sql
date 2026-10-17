-- WUF Predict - esquema inicial PostgreSQL 16 (instalación nueva).
-- Incluye HU01: registro de ejecuciones y snapshots del catálogo.
-- Ejecutar conectado a una base vacía; este archivo no crea la base de datos.

BEGIN;

CREATE TABLE usuario (
    id_usuario SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    rol VARCHAR(20) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL
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
    CONSTRAINT ck_mascota_edad_meses_no_negativa
        CHECK (edad_meses IS NULL OR edad_meses >= 0),
    CONSTRAINT ck_mascota_orden_publicacion_positivo
        CHECK (orden_publicacion > 0)
);

CREATE TABLE etiqueta_condicion (
    id_etiqueta SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL,
    etiqueta VARCHAR(30) NOT NULL,
    CONSTRAINT fk_etiqueta_condicion_mascota
        FOREIGN KEY (id_mascota) REFERENCES mascota (id_mascota)
);

CREATE TABLE adoptante (
    id_adoptante SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL
);

CREATE TABLE adopcion (
    id_adopcion SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL,
    id_adoptante INTEGER NOT NULL,
    fecha_adopcion DATE NOT NULL,
    costo DECIMAL(8,2) NOT NULL,
    estado VARCHAR(20) NOT NULL,
    CONSTRAINT ck_adopcion_costo_no_negativo
        CHECK (costo >= 0),
    CONSTRAINT fk_adopcion_mascota
        FOREIGN KEY (id_mascota) REFERENCES mascota (id_mascota),
    CONSTRAINT fk_adopcion_adoptante
        FOREIGN KEY (id_adoptante) REFERENCES adoptante (id_adoptante)
);

CREATE TABLE dataset_historico (
    id_dataset SERIAL PRIMARY KEY,
    fecha_generacion TIMESTAMP NOT NULL,
    nro_registros INTEGER NOT NULL,
    version VARCHAR(10) NOT NULL,
    origen_etiquetas VARCHAR(20) NOT NULL DEFAULT 'desconocida',
    CONSTRAINT ck_dataset_nro_registros_no_negativo
        CHECK (nro_registros >= 0),
    CONSTRAINT ck_dataset_origen_etiquetas
        CHECK (origen_etiquetas IN ('sintetica', 'verificada', 'inferida', 'mixta', 'desconocida'))
);

CREATE TABLE ejecucion_recoleccion (
    id_ejecucion SERIAL PRIMARY KEY,
    id_usuario INTEGER NULL,
    tipo_ejecucion VARCHAR(15) NOT NULL,
    fuente_datos VARCHAR(24) NOT NULL DEFAULT 'csv_simulada',
    referencia_fuente VARCHAR(255) NULL,
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP NULL,
    semana INTEGER NOT NULL,
    perfiles_total INTEGER NOT NULL DEFAULT 0,
    perfiles_disponibles INTEGER NOT NULL DEFAULT 0,
    perfiles_no_disponibles INTEGER NOT NULL DEFAULT 0,
    perfiles_sin_publicar INTEGER NOT NULL DEFAULT 0,
    estado VARCHAR(15) NOT NULL,
    mensaje_error VARCHAR(1000) NULL,
    CONSTRAINT ck_ejecucion_tipo
        CHECK (tipo_ejecucion IN ('manual', 'programada')),
    CONSTRAINT ck_ejecucion_fuente_datos
        CHECK (fuente_datos = 'csv_simulada'),
    CONSTRAINT ck_ejecucion_semana
        CHECK (semana BETWEEN 1 AND 53),
    CONSTRAINT ck_ejecucion_conteos
        CHECK (
            perfiles_total >= 0
            AND perfiles_disponibles >= 0
            AND perfiles_no_disponibles >= 0
            AND perfiles_sin_publicar >= 0
        ),
    CONSTRAINT ck_ejecucion_estado
        CHECK (estado IN ('en_proceso', 'completada', 'parcial', 'fallida')),
    CONSTRAINT ck_ejecucion_fechas
        CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio),
    CONSTRAINT fk_ejecucion_recoleccion_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
);

CREATE INDEX ix_ejecucion_recoleccion_fecha_inicio
    ON ejecucion_recoleccion (fecha_inicio DESC);

CREATE UNIQUE INDEX uq_ejecucion_csv_referencia
    ON ejecucion_recoleccion (fuente_datos, referencia_fuente)
    WHERE fuente_datos = 'csv_simulada'
      AND referencia_fuente IS NOT NULL
      AND estado IN ('en_proceso', 'completada', 'parcial');

CREATE TABLE snapshot_catalogo (
    id_snapshot SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL,
    id_dataset INTEGER NULL,
    id_ejecucion INTEGER NOT NULL,
    semana INTEGER NOT NULL,
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
    -- La simulación marca etiquetas sintéticas; su origen impide tratarlas como adopciones verificadas.
    etiqueta_adoptado BOOLEAN NULL,
    origen_etiqueta VARCHAR(20) NULL,
    CONSTRAINT ck_snapshot_origen_etiqueta
        CHECK (
            (etiqueta_adoptado IS NULL AND origen_etiqueta IS NULL)
            OR (etiqueta_adoptado IS NOT NULL AND origen_etiqueta IS NOT NULL
                AND origen_etiqueta IN ('sintetica', 'verificada', 'inferida', 'desconocida'))
        ),
    CONSTRAINT ck_snapshot_semana
        CHECK (semana BETWEEN 1 AND 53),
    CONSTRAINT ck_snapshot_edad_meses_no_negativa
        CHECK (edad_meses IS NULL OR edad_meses >= 0),
    CONSTRAINT ck_snapshot_orden_publicacion_positivo
        CHECK (orden_publicacion > 0),
    CONSTRAINT fk_snapshot_catalogo_mascota
        FOREIGN KEY (id_mascota) REFERENCES mascota (id_mascota),
    CONSTRAINT fk_snapshot_catalogo_dataset
        FOREIGN KEY (id_dataset) REFERENCES dataset_historico (id_dataset),
    CONSTRAINT fk_snapshot_catalogo_ejecucion
        FOREIGN KEY (id_ejecucion) REFERENCES ejecucion_recoleccion (id_ejecucion),
    CONSTRAINT uq_snapshot_ejecucion_mascota
        UNIQUE (id_ejecucion, id_mascota)
);

CREATE INDEX ix_snapshot_mascota_fecha_captura
    ON snapshot_catalogo (id_mascota, fecha_captura DESC);

CREATE TABLE snapshot_etiqueta_condicion (
    id_snapshot INTEGER NOT NULL,
    etiqueta VARCHAR(30) NOT NULL,
    CONSTRAINT pk_snapshot_etiqueta_condicion
        PRIMARY KEY (id_snapshot, etiqueta),
    CONSTRAINT fk_snapshot_etiqueta_condicion_snapshot
        FOREIGN KEY (id_snapshot) REFERENCES snapshot_catalogo (id_snapshot)
);

CREATE TABLE modelo_predictivo (
    id_modelo SERIAL PRIMARY KEY,
    id_dataset INTEGER NOT NULL,
    algoritmo VARCHAR(30) NOT NULL,
    version VARCHAR(10) NOT NULL,
    accuracy_score DECIMAL(5,4) NOT NULL,
    precision_score DECIMAL(5,4) NOT NULL,
    recall_score DECIMAL(5,4) NOT NULL,
    f1_score DECIMAL(5,4) NOT NULL,
    fecha_entrenamiento TIMESTAMP NOT NULL,
    CONSTRAINT ck_modelo_metricas_rango
        CHECK (
            accuracy_score BETWEEN 0 AND 1
            AND precision_score BETWEEN 0 AND 1
            AND recall_score BETWEEN 0 AND 1
            AND f1_score BETWEEN 0 AND 1
        ),
    CONSTRAINT fk_modelo_predictivo_dataset
        FOREIGN KEY (id_dataset) REFERENCES dataset_historico (id_dataset)
);

CREATE TABLE reporte_priorizacion (
    id_reporte SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL,
    semana INTEGER NOT NULL,
    fecha_generacion TIMESTAMP NOT NULL,
    formato VARCHAR(10) NOT NULL,
    CONSTRAINT ck_reporte_semana
        CHECK (semana BETWEEN 1 AND 53),
    CONSTRAINT fk_reporte_priorizacion_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
);

CREATE TABLE prediccion (
    id_prediccion SERIAL PRIMARY KEY,
    id_modelo INTEGER NOT NULL,
    id_mascota INTEGER NOT NULL,
    id_reporte INTEGER NULL,
    probabilidad_adopcion DECIMAL(5,4) NOT NULL,
    nivel_prioridad VARCHAR(10) NOT NULL,
    fecha TIMESTAMP NOT NULL,
    CONSTRAINT ck_prediccion_probabilidad_rango
        CHECK (probabilidad_adopcion BETWEEN 0 AND 1),
    CONSTRAINT fk_prediccion_modelo
        FOREIGN KEY (id_modelo) REFERENCES modelo_predictivo (id_modelo),
    CONSTRAINT fk_prediccion_mascota
        FOREIGN KEY (id_mascota) REFERENCES mascota (id_mascota),
    CONSTRAINT fk_prediccion_reporte
        FOREIGN KEY (id_reporte) REFERENCES reporte_priorizacion (id_reporte)
);

CREATE TABLE alerta_desactualizacion (
    id_alerta SERIAL PRIMARY KEY,
    id_mascota INTEGER NOT NULL,
    fecha TIMESTAMP NOT NULL,
    nivel_riesgo VARCHAR(10) NOT NULL,
    mensaje VARCHAR(255) NOT NULL,
    estado VARCHAR(15) NOT NULL,
    CONSTRAINT fk_alerta_desactualizacion_mascota
        FOREIGN KEY (id_mascota) REFERENCES mascota (id_mascota)
);

COMMIT;
