-- HU01: cambia la fuente futura a CSV y registra el archivo usado por cada ejecución.
-- Conserva la historia existente, incluidas ejecuciones marcadas como WUF/base local.
-- Ejecutar una sola vez después de las migraciones HU01 anteriores.

BEGIN;

-- Elimina solo la captura WUF fallida que el propietario identificó como prueba,
-- y únicamente si no tiene snapshots. Otras ejecuciones se conservan.
DELETE FROM ejecucion_recoleccion AS ejecucion
WHERE ejecucion.id_ejecucion = 1
  AND ejecucion.estado = 'fallida'
  AND ejecucion.fuente_datos = 'wuf'
  AND ejecucion.perfiles_total = 189
  AND NOT EXISTS (
    SELECT 1
    FROM snapshot_catalogo AS snapshot
    WHERE snapshot.id_ejecucion = ejecucion.id_ejecucion
  );

-- El SKU estable es la clave de reconciliación de una mascota entre archivos.
CREATE UNIQUE INDEX uq_mascota_sku
    ON mascota (sku);

ALTER TABLE ejecucion_recoleccion
    ADD COLUMN referencia_fuente VARCHAR(255) NULL;

ALTER TABLE ejecucion_recoleccion
    ALTER COLUMN fuente_datos SET DEFAULT 'csv_simulada';

ALTER TABLE ejecucion_recoleccion
    DROP CONSTRAINT IF EXISTS ck_ejecucion_fuente_datos;

ALTER TABLE ejecucion_recoleccion
    ADD CONSTRAINT ck_ejecucion_fuente_datos
        CHECK (fuente_datos IN ('csv_simulada', 'wuf', 'base_local_simulada'));

CREATE UNIQUE INDEX uq_ejecucion_csv_referencia
    ON ejecucion_recoleccion (fuente_datos, referencia_fuente)
    WHERE fuente_datos = 'csv_simulada'
      AND referencia_fuente IS NOT NULL
      AND estado IN ('en_proceso', 'completada', 'parcial');

ALTER TABLE snapshot_catalogo
    ADD COLUMN origen_etiqueta VARCHAR(20) NULL;

-- El origen de etiquetas antiguas no se puede reconstruir; se registra como desconocido.
UPDATE snapshot_catalogo
SET origen_etiqueta = 'desconocida'
WHERE etiqueta_adoptado IS NOT NULL;

ALTER TABLE snapshot_catalogo
    ADD CONSTRAINT ck_snapshot_origen_etiqueta
        CHECK (
            (etiqueta_adoptado IS NULL AND origen_etiqueta IS NULL)
            OR (etiqueta_adoptado IS NOT NULL AND origen_etiqueta IS NOT NULL
                AND origen_etiqueta IN ('sintetica', 'verificada', 'inferida', 'desconocida'))
        );

-- Permite a HU03 distinguir datasets experimentales de los construidos con etiquetas verificadas.
ALTER TABLE dataset_historico
    ADD COLUMN origen_etiquetas VARCHAR(20) NOT NULL DEFAULT 'desconocida',
    ADD CONSTRAINT ck_dataset_origen_etiquetas
        CHECK (origen_etiquetas IN ('sintetica', 'verificada', 'inferida', 'mixta', 'desconocida'));

COMMIT;
