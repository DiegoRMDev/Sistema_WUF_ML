-- WUF Predict - actualización aditiva de HU01 para una base ya creada
-- en PostgreSQL 16 mediante backend/schema.sql anterior.
-- Ejecutar una sola vez, conectado a la base existente wuf_predict.
-- No elimina ni reemplaza datos.

BEGIN;

CREATE TABLE ejecucion_recoleccion (
    id_ejecucion SERIAL PRIMARY KEY,
    id_usuario INTEGER NULL,
    tipo_ejecucion VARCHAR(15) NOT NULL,
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

ALTER TABLE snapshot_catalogo
    ADD COLUMN id_ejecucion INTEGER NULL,
    ADD COLUMN sku VARCHAR(10) NULL,
    ADD COLUMN nombre VARCHAR(80) NULL,
    ADD COLUMN especie VARCHAR(10) NULL,
    ADD COLUMN raza VARCHAR(30) NULL,
    ADD COLUMN sexo CHAR(1) NULL,
    ADD COLUMN edad_meses INTEGER NULL,
    ADD COLUMN edad_estimada BOOLEAN NULL,
    ADD COLUMN tipo_pelaje VARCHAR(15) NULL,
    ADD COLUMN tamano VARCHAR(10) NULL,
    ADD COLUMN tamano_estimado BOOLEAN NULL,
    ADD COLUMN nivel_energia VARCHAR(10) NULL,
    ADD COLUMN condicion_especial BOOLEAN NULL,
    ADD COLUMN condicion_detalle VARCHAR(200) NULL,
    ADD COLUMN descripcion VARCHAR(512) NULL,
    ADD COLUMN orden_publicacion INTEGER NULL,
    ADD COLUMN fecha_publicacion DATE NULL,
    ADD COLUMN url_perfil VARCHAR(255) NULL;

ALTER TABLE snapshot_catalogo
    ADD CONSTRAINT fk_snapshot_catalogo_ejecucion
        FOREIGN KEY (id_ejecucion) REFERENCES ejecucion_recoleccion (id_ejecucion),
    ADD CONSTRAINT uq_snapshot_ejecucion_mascota
        UNIQUE (id_ejecucion, id_mascota),
    ADD CONSTRAINT ck_snapshot_edad_meses_no_negativa
        CHECK (edad_meses IS NULL OR edad_meses >= 0),
    ADD CONSTRAINT ck_snapshot_orden_publicacion_positivo
        CHECK (orden_publicacion IS NULL OR orden_publicacion > 0),
    ADD CONSTRAINT ck_snapshot_hu01_completo
        CHECK (
            id_ejecucion IS NULL
            OR (
                sku IS NOT NULL
                AND nombre IS NOT NULL
                AND especie IS NOT NULL
                AND raza IS NOT NULL
                AND sexo IS NOT NULL
                AND edad_estimada IS NOT NULL
                AND tipo_pelaje IS NOT NULL
                AND tamano IS NOT NULL
                AND tamano_estimado IS NOT NULL
                AND nivel_energia IS NOT NULL
                AND condicion_especial IS NOT NULL
                AND orden_publicacion IS NOT NULL
                AND fecha_publicacion IS NOT NULL
                AND url_perfil IS NOT NULL
            )
        ) NOT VALID;

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

COMMIT;
