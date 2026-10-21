"""Consultas PostgreSQL de datasets, versiones de modelo y predicciones HU03."""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.model_training import TrainingResult
from app.infrastructure.model_artifact_storage import ModelArtifactStorage


class ModelRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_dataset_options(self) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            SELECT h.id_dataset, h.version, h.fecha_desde, h.fecha_hasta, h.origen_etiquetas,
                   COUNT(d.id_dataset_detalle) AS registros,
                   COUNT(*) FILTER (WHERE d.etiqueta_catalogo='permanece') AS permanece,
                   COUNT(*) FILTER (WHERE d.etiqueta_catalogo='salio_catalogo') AS salio_catalogo,
                   COUNT(*) FILTER (WHERE d.etiqueta_catalogo='indeterminada') AS indeterminada
            FROM dataset_historico h
            JOIN dataset_detalle d ON d.id_dataset=h.id_dataset
            GROUP BY h.id_dataset
            ORDER BY h.id_dataset DESC
        """)).mappings().all()
        return [dict(row) for row in rows]

    def get_training_rows(self, dataset_id: int) -> list[dict[str, Any]] | None:
        exists = self._session.execute(text(
            "SELECT 1 FROM dataset_historico WHERE id_dataset=:dataset_id"
        ), {"dataset_id": dataset_id}).scalar_one_or_none()
        if exists is None:
            return None
        rows = self._session.execute(text("""
            SELECT ref.sku, ref.especie, ref.raza, ref.sexo, ref.edad_meses,
                   ref.edad_estimada, ref.tipo_pelaje, ref.tamano, ref.tamano_estimado,
                   ref.nivel_energia, ref.condicion_especial, ref.orden_publicacion,
                   d.etiqueta_catalogo, d.motivo_indeterminado
            FROM dataset_detalle d
            JOIN snapshot_catalogo ref ON ref.id_snapshot=d.id_snapshot_referencia
            WHERE d.id_dataset=:dataset_id
            ORDER BY ref.sku
        """), {"dataset_id": dataset_id}).mappings().all()
        return [dict(row) for row in rows]

    def save_candidate(
        self, dataset_id: int, result: TrainingResult, threshold: float,
        artifact_storage: ModelArtifactStorage,
    ) -> int:
        """Registra primero la evaluación y vincula su artefacto dentro de una transacción."""
        model_id: int | None = None
        artifact_name: str | None = None
        try:
            model_id = int(self._session.execute(text("""
                INSERT INTO modelo_predictivo
                    (id_dataset, algoritmo, version, accuracy_score, precision_score,
                     recall_score, f1_score, fecha_entrenamiento, estado,
                     metadatos_entrenamiento, clase_positiva, nro_registros_entrenamiento,
                     nro_registros_prueba, nro_registros_excluidos, umbral_accuracy,
                     matriz_confusion, importancia_variables)
                VALUES (:dataset_id, 'RandomForestClassifier', 'pendiente', :accuracy,
                        :precision, :recall, :f1,
                        (CURRENT_TIMESTAMP AT TIME ZONE 'America/Lima'), :estado,
                        CAST(:metadata AS JSONB), 'salio_catalogo', :train_count,
                        :test_count, :excluded_count, :threshold,
                        CAST(:confusion AS JSONB), CAST(:importance AS JSONB))
                RETURNING id_modelo
            """), {
                "dataset_id": dataset_id,
                "accuracy": result.metrics["accuracy"],
                "precision": result.metrics["precision"],
                "recall": result.metrics["recall"],
                "f1": result.metrics["f1"],
                "estado": "publicable" if result.metrics["accuracy"] >= threshold else "no_publicable",
                "metadata": json.dumps({
                    **result.parameters,
                    "clase_positiva": "salio_catalogo",
                    "interpretacion_probabilidad": "proxy_salida_catalogo",
                    "conteo_clases": result.class_counts,
                    "motivos_excluidos": result.excluded_reasons,
                    "precision_probabilidades": "sin_calibrar",
                }),
                "train_count": result.train_count,
                "test_count": result.test_count,
                "excluded_count": result.excluded_count,
                "threshold": threshold,
                "confusion": json.dumps(result.confusion),
                "importance": json.dumps(result.feature_importance),
            }).scalar_one())
            self._session.execute(text(
                "UPDATE modelo_predictivo SET version=:version WHERE id_modelo=:model_id"
            ), {"version": f"v{model_id}", "model_id": model_id})

            # El nombre se genera en el servidor; nunca se acepta una ruta desde el navegador.
            artifact_name, digest = artifact_storage.save(model_id, result.pipeline)
            self._session.execute(text("""
                UPDATE modelo_predictivo
                SET artefacto_ruta=:filename, artefacto_sha256=:digest
                WHERE id_modelo=:model_id
            """), {"filename": artifact_name, "digest": digest, "model_id": model_id})
            self._session.commit()
            return model_id
        except Exception:
            self._session.rollback()
            if artifact_name:
                artifact_storage.delete(artifact_name)
            raise

    def list_models(self) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            SELECT m.id_modelo, m.version, m.algoritmo, m.estado, m.es_vigente,
                   m.id_dataset, d.version AS dataset_version, m.accuracy_score,
                   m.precision_score, m.recall_score, m.f1_score, m.fecha_entrenamiento,
                   m.nro_registros_entrenamiento, m.nro_registros_prueba,
                   m.nro_registros_excluidos, m.umbral_accuracy,
                   m.clase_positiva, m.matriz_confusion, m.importancia_variables,
                   m.metadatos_entrenamiento
            FROM modelo_predictivo m
            JOIN dataset_historico d ON d.id_dataset=m.id_dataset
            ORDER BY m.id_modelo DESC
        """)).mappings().all()
        return [dict(row) for row in rows]

    def get_model(self, model_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            SELECT m.*, d.version AS dataset_version
            FROM modelo_predictivo m
            JOIN dataset_historico d ON d.id_dataset=m.id_dataset
            WHERE m.id_modelo=:model_id
        """), {"model_id": model_id}).mappings().first()
        return dict(row) if row else None

    def get_available_pets(self) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            WITH latest_capture AS (
                SELECT id_ejecucion FROM ejecucion_recoleccion
                WHERE estado='completada'
                ORDER BY fecha_captura DESC, id_ejecucion DESC
                LIMIT 1
            )
            SELECT snapshot.id_ejecucion, snapshot.id_mascota, snapshot.sku, snapshot.especie, snapshot.raza,
                   snapshot.sexo, snapshot.edad_meses, snapshot.edad_estimada,
                   snapshot.tipo_pelaje, snapshot.tamano, snapshot.tamano_estimado,
                   snapshot.nivel_energia, snapshot.condicion_especial,
                   snapshot.orden_publicacion
            FROM snapshot_catalogo snapshot
            JOIN latest_capture run ON run.id_ejecucion=snapshot.id_ejecucion
            WHERE snapshot.estado_detectado='disponible'
            ORDER BY snapshot.sku
        """)).mappings().all()
        return [dict(row) for row in rows]

    def get_catalog_predictions(self) -> dict[str, Any]:
        """Entrega el catálogo vigente y solo predicciones del modelo publicado actualmente."""
        schema_ready = self._session.execute(text("""
            SELECT COUNT(*) = 4
            FROM information_schema.columns
            WHERE table_schema=current_schema()
              AND (table_name, column_name) IN (
                  ('ejecucion_recoleccion', 'fecha_captura'),
                  ('modelo_predictivo', 'es_vigente'),
                  ('prediccion', 'id_ejecucion'),
                  ('snapshot_catalogo', 'id_ejecucion')
              )
        """)).scalar_one()
        if not schema_ready:
            return {
                "items": [],
                "modelo_version": None,
                "mensaje": "Las predicciones del catálogo requieren una base v2/v3 con la migración HU03 aplicada.",
            }
        rows = self._session.execute(text("""
            WITH latest_capture AS (
                SELECT id_ejecucion FROM ejecucion_recoleccion
                WHERE estado='completada'
                ORDER BY fecha_captura DESC, id_ejecucion DESC
                LIMIT 1
            )
            SELECT snapshot.id_mascota, snapshot.sku, snapshot.nombre, snapshot.especie,
                   snapshot.sexo, snapshot.edad_meses, snapshot.edad_estimada,
                   snapshot.tipo_pelaje, snapshot.tamano, snapshot.nivel_energia,
                   snapshot.condicion_especial, snapshot.condicion_detalle,
                   snapshot.orden_publicacion, snapshot.estado_detectado AS estado_publicado,
                   prediction.probabilidad_adopcion, prediction.nivel_prioridad,
                   model.version AS modelo_version
            FROM snapshot_catalogo snapshot
            JOIN latest_capture run ON run.id_ejecucion=snapshot.id_ejecucion
            LEFT JOIN modelo_predictivo model ON model.es_vigente=TRUE
            LEFT JOIN prediccion prediction
              ON prediction.id_modelo=model.id_modelo
             AND prediction.id_mascota=snapshot.id_mascota
             AND prediction.id_ejecucion=run.id_ejecucion
             AND prediction.id_reporte IS NULL
            ORDER BY snapshot.orden_publicacion DESC, snapshot.sku
        """)).mappings().all()
        return {"items": [dict(row) for row in rows],
                "modelo_version": rows[0]["modelo_version"] if rows else None,
                "mensaje": None}

    def activate_model(
        self, model_id: int, predictions: list[dict[str, Any]],
    ) -> None:
        """Actualiza predicciones vigentes y publica el modelo en la misma transacción."""
        try:
            candidate = self.get_model(model_id)
            if candidate is None:
                raise LookupError("No se encontró el modelo solicitado.")
            if candidate["estado"] != "publicable":
                raise ValueError("Este modelo no alcanza el umbral de publicación configurado.")

            # Reemplaza únicamente predicciones sueltas de este modelo; los reportes históricos permanecen.
            self._session.execute(text(
                "DELETE FROM prediccion WHERE id_modelo=:model_id AND id_reporte IS NULL"
            ), {"model_id": model_id})
            for prediction in predictions:
                self._session.execute(text("""
                    INSERT INTO prediccion
                    (id_modelo, id_mascota, id_ejecucion, id_reporte, probabilidad_adopcion,
                         nivel_prioridad, fecha)
                    VALUES (:model_id, :pet_id, :run_id, NULL, :probability, :priority, CURRENT_TIMESTAMP)
                """), {
                    "model_id": model_id,
                    "pet_id": prediction["id_mascota"],
                    "run_id": prediction["id_ejecucion"],
                    "probability": prediction["probability"],
                    "priority": prediction["priority"],
                })

            self._session.execute(text(
                "UPDATE modelo_predictivo SET es_vigente=FALSE, estado='publicado' WHERE es_vigente=TRUE"
            ))
            self._session.execute(text("""
                UPDATE modelo_predictivo
                SET es_vigente=TRUE, estado='vigente'
                WHERE id_modelo=:model_id
            """), {"model_id": model_id})
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def refresh_predictions(self, model_id: int, predictions: list[dict[str, Any]]) -> None:
        """Renueva la evaluación para la última captura sin cambiar el modelo vigente."""
        try:
            model = self.get_model(model_id)
            if model is None or not model["es_vigente"]:
                raise ValueError("Solo se pueden actualizar predicciones del modelo vigente.")
            self._session.execute(text(
                "DELETE FROM prediccion WHERE id_modelo=:model_id AND id_reporte IS NULL"
            ), {"model_id": model_id})
            for prediction in predictions:
                self._session.execute(text("""
                    INSERT INTO prediccion
                        (id_modelo, id_mascota, id_ejecucion, id_reporte,
                         probabilidad_adopcion, nivel_prioridad, fecha)
                    VALUES (:model_id, :pet_id, :run_id, NULL,
                            :probability, :priority, CURRENT_TIMESTAMP)
                """), {
                    "model_id": model_id,
                    "pet_id": prediction["id_mascota"],
                    "run_id": prediction["id_ejecucion"],
                    "probability": prediction["probability"],
                    "priority": prediction["priority"],
                })
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

