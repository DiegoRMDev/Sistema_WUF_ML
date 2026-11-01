"""Consultas agregadas de solo lectura para el Dashboard HU08."""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardRepository:
    """Lee capturas y resultados ya guardados por HU01–HU07; no crea datos nuevos."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def completed_runs(self, limit: int) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            SELECT run.id_ejecucion, run.fecha_captura, run.semana,
                   COUNT(snapshot.id_snapshot) AS perfiles_total,
                   COUNT(snapshot.id_snapshot) FILTER (
                       WHERE snapshot.estado_detectado = 'disponible'
                   ) AS perfiles_disponibles,
                   COUNT(snapshot.id_snapshot) FILTER (
                       WHERE snapshot.estado_detectado = 'no_disponible'
                   ) AS perfiles_no_disponibles,
                   COUNT(snapshot.id_snapshot) FILTER (
                       WHERE snapshot.estado_detectado = 'sin_publicar'
                   ) AS perfiles_sin_publicar
            FROM ejecucion_recoleccion AS run
            LEFT JOIN snapshot_catalogo AS snapshot ON snapshot.id_ejecucion = run.id_ejecucion
            WHERE run.estado = 'completada'
            GROUP BY run.id_ejecucion
            ORDER BY run.fecha_captura DESC, run.id_ejecucion DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def disadvantaged_count(self, run_id: int) -> int:
        return int(self._session.execute(text("""
            SELECT COUNT(*)
            FROM snapshot_catalogo
            WHERE id_ejecucion = :run_id
              AND estado_detectado = 'disponible'
              AND (
                  (edad_meses IS NOT NULL AND edad_meses >= 96)
                  OR LOWER(tamano) = 'grande'
                  OR condicion_especial = TRUE
              )
        """), {"run_id": run_id}).scalar_one())

    def adoption_metrics(self, run_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            WITH selected_model AS (
                SELECT model.id_modelo, model.version
                FROM prediccion AS prediction
                JOIN modelo_predictivo AS model ON model.id_modelo = prediction.id_modelo
                WHERE prediction.id_ejecucion = :run_id
                  AND prediction.id_reporte IS NULL
                GROUP BY model.id_modelo, model.version
                ORDER BY MAX(prediction.fecha) DESC, model.id_modelo DESC
                LIMIT 1
            )
            SELECT selected_model.version,
                   COUNT(DISTINCT prediction.id_mascota) AS predicciones,
                   COUNT(DISTINCT prediction.id_mascota) FILTER (
                       WHERE LOWER(prediction.nivel_prioridad) = 'alta'
                   ) AS prioridad_alta,
                   COUNT(DISTINCT prediction.id_mascota) FILTER (
                       WHERE LOWER(prediction.nivel_prioridad) = 'media'
                   ) AS prioridad_media,
                   COUNT(DISTINCT prediction.id_mascota) FILTER (
                       WHERE LOWER(prediction.nivel_prioridad) = 'baja'
                   ) AS prioridad_baja
            FROM selected_model
            JOIN prediccion AS prediction ON prediction.id_modelo = selected_model.id_modelo
            WHERE prediction.id_ejecucion = :run_id
              AND prediction.id_reporte IS NULL
            GROUP BY selected_model.id_modelo, selected_model.version
        """), {"run_id": run_id}).mappings().first()
        return dict(row) if row else None

    def high_alert_count(self) -> int:
        return int(self._session.execute(text("""
            SELECT COUNT(*)
            FROM alerta_desactualizacion
            WHERE nivel_riesgo = 'alto'
              AND estado IN ('pendiente', 'en_revision')
        """)).scalar_one())

    def segmentation_metrics(self, run_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            WITH applied_model AS (
                SELECT model.id_modelo_segmentacion, model.version,
                       model.cantidad_clusters, model.silhouette_score,
                       MAX(assignment.fecha_asignacion) AS applied_at
                FROM modelo_segmentacion AS model
                JOIN asignacion_segmento AS assignment
                  ON assignment.id_modelo_segmentacion = model.id_modelo_segmentacion
                JOIN snapshot_catalogo AS snapshot ON snapshot.id_snapshot = assignment.id_snapshot
                WHERE snapshot.id_ejecucion = :run_id
                  AND snapshot.estado_detectado = 'disponible'
                  AND model.parametros->>'cohort_scope' = 'all_available_v1'
                GROUP BY model.id_modelo_segmentacion, model.version,
                         model.cantidad_clusters, model.silhouette_score
                ORDER BY MAX(assignment.fecha_asignacion) DESC,
                         model.id_modelo_segmentacion DESC
                LIMIT 1
            )
            SELECT applied_model.version, applied_model.cantidad_clusters,
                   applied_model.silhouette_score,
                   COUNT(DISTINCT assignment.id_snapshot) AS perfiles_asignados,
                   COUNT(DISTINCT assignment.id_snapshot) FILTER (
                       WHERE jsonb_array_length(assignment.criterios_desfavorecidos) > 0
                   ) AS perfiles_desfavorecidos_asignados
            FROM applied_model
            JOIN asignacion_segmento AS assignment
              ON assignment.id_modelo_segmentacion = applied_model.id_modelo_segmentacion
            JOIN snapshot_catalogo AS snapshot ON snapshot.id_snapshot = assignment.id_snapshot
            WHERE snapshot.id_ejecucion = :run_id
              AND snapshot.estado_detectado = 'disponible'
            GROUP BY applied_model.version, applied_model.cantidad_clusters,
                     applied_model.silhouette_score
        """), {"run_id": run_id}).mappings().first()
        if row is None:
            return None
        return {
            "version": row["version"],
            "segmentos": int(row["cantidad_clusters"]),
            "silhouette": float(row["silhouette_score"]),
            "perfiles_asignados": int(row["perfiles_asignados"]),
            "perfiles_desfavorecidos_asignados": int(row["perfiles_desfavorecidos_asignados"]),
        }

    def consistency_metrics(self, run_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            SELECT model.version,
                   COUNT(evaluation.id_evaluacion) AS perfiles_evaluados,
                   COUNT(evaluation.id_evaluacion) FILTER (
                       WHERE evaluation.nivel_riesgo = 'alto'
                   ) AS riesgo_alto
            FROM modelo_consistencia AS model
            JOIN evaluacion_consistencia AS evaluation
              ON evaluation.id_modelo_consistencia = model.id_modelo_consistencia
            WHERE evaluation.id_ejecucion = :run_id
            GROUP BY model.id_modelo_consistencia, model.version, model.fecha_entrenamiento
            ORDER BY model.fecha_entrenamiento DESC, model.id_modelo_consistencia DESC
            LIMIT 1
        """), {"run_id": run_id}).mappings().first()
        return dict(row) if row else None

    def recent_activity(self, limit: int) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            SELECT activity.fecha, activity.accion, activity.detalle
            FROM (
                SELECT COALESCE(run.fecha_fin, run.fecha_inicio) AS fecha,
                       'Captura CSV importada'::VARCHAR AS accion,
                       ('Semana ' || run.semana || ' · ' || run.perfiles_total || ' perfiles')::VARCHAR AS detalle
                FROM ejecucion_recoleccion AS run
                WHERE run.estado = 'completada'
                UNION ALL
                SELECT dataset.fecha_generacion,
                       'Dataset histórico generado'::VARCHAR,
                       ('Versión ' || dataset.version || ' · ' || dataset.nro_registros || ' registros')::VARCHAR
                FROM dataset_historico AS dataset
                UNION ALL
                SELECT model.fecha_entrenamiento,
                       'Random Forest entrenado'::VARCHAR,
                       ('Versión ' || model.version || ' · ' || model.estado)::VARCHAR
                FROM modelo_predictivo AS model
                UNION ALL
                SELECT model.fecha_entrenamiento,
                       'Árbol de decisión entrenado'::VARCHAR,
                       ('Versión ' || model.version)::VARCHAR
                FROM modelo_consistencia AS model
                UNION ALL
                SELECT model.fecha_entrenamiento,
                       'Segmentación K-Means entrenada'::VARCHAR,
                       ('Versión ' || model.version || ' · ' || model.cantidad_clusters || ' segmentos')::VARCHAR
                FROM modelo_segmentacion AS model
                UNION ALL
                SELECT report.fecha_generacion,
                       'Reporte de priorización exportado'::VARCHAR,
                       UPPER(report.formato)::VARCHAR
                FROM reporte_priorizacion AS report
                UNION ALL
                SELECT alert.fecha,
                       'Alerta de riesgo alto generada'::VARCHAR,
                       ('Semana ' || run.semana)::VARCHAR
                FROM alerta_desactualizacion AS alert
                JOIN evaluacion_consistencia AS evaluation
                  ON evaluation.id_evaluacion = alert.id_evaluacion_origen
                JOIN ejecucion_recoleccion AS run ON run.id_ejecucion = evaluation.id_ejecucion
                WHERE alert.nivel_riesgo = 'alto'
                UNION ALL
                SELECT attention.fecha,
                       'Alerta atendida'::VARCHAR,
                       ('Estado: ' || REPLACE(attention.estado_nuevo, '_', ' '))::VARCHAR
                FROM alerta_atencion AS attention
            ) AS activity
            ORDER BY activity.fecha DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]
