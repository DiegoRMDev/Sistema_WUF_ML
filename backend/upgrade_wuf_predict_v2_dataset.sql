BEGIN;

-- Registra también las ejecuciones completas que sirven para detectar perfiles ausentes.
CREATE TABLE IF NOT EXISTS dataset_ejecucion (
    id_dataset INTEGER NOT NULL REFERENCES dataset_historico (id_dataset) ON DELETE CASCADE,
    id_ejecucion INTEGER NOT NULL REFERENCES ejecucion_recoleccion (id_ejecucion),
    PRIMARY KEY (id_dataset, id_ejecucion)
);

-- El prototipo etiqueta como "Salió" un perfil cuyo estado final es "No disponible";
-- por eso puede existir un snapshot de resultado para esa clase.
ALTER TABLE dataset_detalle
    DROP CONSTRAINT IF EXISTS ck_dataset_detalle_evidencia;

ALTER TABLE dataset_detalle
    ADD CONSTRAINT ck_dataset_detalle_evidencia CHECK (
        (etiqueta_catalogo = 'permanece'
            AND id_ejecucion_resultado IS NOT NULL AND id_snapshot_resultado IS NOT NULL)
        OR (etiqueta_catalogo = 'salio_catalogo' AND id_ejecucion_resultado IS NOT NULL)
        OR etiqueta_catalogo = 'indeterminada'
    );

COMMIT;
