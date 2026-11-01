"""Consultas y persistencia del reporte HU05 en PostgreSQL."""

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_current_source(self) -> dict[str, Any]:
        """Obtiene las predicciones vigentes y las valida contra la última captura completa."""
        run = self._session.execute(text("""
            SELECT id_ejecucion, fecha_captura, semana, perfiles_disponibles
            FROM ejecucion_recoleccion
            WHERE estado='completada'
            ORDER BY fecha_captura DESC, id_ejecucion DESC
            LIMIT 1
        """)).mappings().first()
        if run is None:
            return {"estado": "sin_capturas", "mensaje": "Todavía no hay capturas completas para generar un reporte."}

        model = self._session.execute(text("""
            SELECT id_modelo, version
            FROM modelo_predictivo
            WHERE es_vigente=TRUE
            LIMIT 1
        """)).mappings().first()
        if model is None:
            return {"estado": "sin_modelo", "mensaje": "Publica un modelo de adopción antes de generar el reporte."}

        counts = self._session.execute(text("""
            SELECT COUNT(*) AS disponibles
            FROM snapshot_catalogo
            WHERE id_ejecucion=:run_id AND estado_detectado='disponible'
        """), {"run_id": run["id_ejecucion"]}).mappings().one()
        available_count = int(counts["disponibles"])
        if available_count == 0:
            return {"estado": "sin_mascotas", "mensaje": "La última captura no contiene mascotas disponibles."}

        rows = self._session.execute(text("""
            SELECT pet.id_mascota, pet.sku, pet.nombre, pet.especie, pet.sexo,
                   pet.edad_meses, pet.edad_estimada, pet.tamano, pet.tamano_estimado,
                   pet.condicion_especial, pet.condicion_detalle, pet.orden_publicacion,
                   prediction.probabilidad_adopcion, prediction.nivel_prioridad
            FROM snapshot_catalogo pet
            JOIN prediccion prediction
              ON prediction.id_mascota=pet.id_mascota
             AND prediction.id_modelo=:model_id
             AND prediction.id_ejecucion=pet.id_ejecucion
             AND prediction.id_reporte IS NULL
            WHERE pet.id_ejecucion=:run_id
              AND pet.estado_detectado='disponible'
            ORDER BY CASE LOWER(prediction.nivel_prioridad)
                         WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baja' THEN 3 ELSE 4 END,
                     prediction.probabilidad_adopcion ASC,
                     pet.orden_publicacion DESC, pet.sku
        """), {"run_id": run["id_ejecucion"], "model_id": model["id_modelo"]}).mappings().all()

        # El reporte solo se considera listo si cada perfil disponible tiene una predicción única.
        if len(rows) != available_count or len({row["id_mascota"] for row in rows}) != available_count:
            return {
                "estado": "predicciones_pendientes",
                "mensaje": "Actualiza las predicciones del modelo vigente para la última captura antes de generar el reporte.",
            }
        if any(str(row["nivel_prioridad"]).casefold() not in {"alta", "media", "baja"} for row in rows):
            return {"estado": "prioridad_invalida", "mensaje": "Hay prioridades incompletas; actualiza las predicciones antes de exportar."}

        segment_model = self._session.execute(text("""
            SELECT id_modelo_segmentacion, version, cantidad_clusters, silhouette_score,
                   resumen_clusters, parametros, es_vigente
            FROM modelo_segmentacion WHERE es_vigente=TRUE LIMIT 1
        """)).mappings().first()
        disadvantaged_count = int(self._session.execute(text("""
            SELECT COUNT(*) FROM snapshot_catalogo
            WHERE id_ejecucion=:run_id AND estado_detectado='disponible'
              AND ((edad_meses IS NOT NULL AND edad_meses >= 96)
                   OR LOWER(tamano)='grande' OR condicion_especial=TRUE)
        """), {"run_id": run["id_ejecucion"]}).scalar_one())
        oe3_items: list[dict[str, Any]] = []
        oe3_state = "sin_modelo"
        full_catalog_model = bool(
            segment_model
            and (segment_model["parametros"] or {}).get("cohort_scope") == "all_available_v1"
        )
        if segment_model is not None and not full_catalog_model:
            # Conserva la versión previa en el historial, pero exige una nueva para el alcance actual.
            oe3_state = "requiere_reentrenamiento"
        elif full_catalog_model:
            assignments = self._session.execute(text("""
                SELECT assignment.id_asignacion_segmento, assignment.id_snapshot,
                       assignment.numero_segmento, assignment.criterios_desfavorecidos,
                       snapshot.sku, snapshot.nombre, snapshot.edad_meses,
                       snapshot.edad_estimada, snapshot.tamano, snapshot.tamano_estimado,
                       snapshot.nivel_energia, snapshot.condicion_especial,
                       snapshot.condicion_detalle, model.version, model.resumen_clusters
                FROM asignacion_segmento assignment
                JOIN snapshot_catalogo snapshot ON snapshot.id_snapshot=assignment.id_snapshot
                JOIN modelo_segmentacion model
                  ON model.id_modelo_segmentacion=assignment.id_modelo_segmentacion
                WHERE model.id_modelo_segmentacion=:model_id
                  AND snapshot.id_ejecucion=:run_id
                  AND snapshot.estado_detectado='disponible'
                ORDER BY assignment.numero_segmento, snapshot.sku
            """), {"model_id": segment_model["id_modelo_segmentacion"],
                   "run_id": run["id_ejecucion"]}).mappings().all()
            oe3_items = [dict(row) for row in assignments]
            oe3_state = "listo" if len(oe3_items) == available_count else "pendiente_actualizacion"

        return {
            "estado": "listo",
            "captura": dict(run),
            "modelo": dict(model),
            "items": [dict(row) for row in rows],
            "total": available_count,
            "oe3": {
                "estado": oe3_state,
                "cantidad_perfiles_disponibles": available_count,
                "cantidad_desfavorecida": disadvantaged_count,
                "modelo": dict(segment_model) if full_catalog_model else None,
                "items": oe3_items,
            },
        }

    def get_report_history(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """Lista exportaciones guardadas que tienen sus filas de predicción asociadas."""
        actor_name_column = (
            "report.nombre_usuario_generador"
            if self._has_report_name_snapshot() else "account.nombre"
        )
        rows = self._session.execute(text(f"""
            SELECT report.id_reporte, report.semana, report.fecha_generacion, report.formato,
                   {actor_name_column} AS usuario, model.version AS modelo_version,
                   segment_model.version AS segmentacion_version,
                   COUNT(DISTINCT prediction.id_prediccion) AS total_oe1,
                   COUNT(DISTINCT report_segment.id_asignacion_segmento) AS total_oe3
            FROM reporte_priorizacion report
            JOIN usuario account ON account.id_usuario=report.id_usuario
            JOIN prediccion prediction ON prediction.id_reporte=report.id_reporte
            JOIN modelo_predictivo model ON model.id_modelo=prediction.id_modelo
            LEFT JOIN modelo_segmentacion segment_model
              ON segment_model.id_modelo_segmentacion=report.id_modelo_segmentacion
            LEFT JOIN reporte_segmento_detalle report_segment
              ON report_segment.id_reporte=report.id_reporte
            GROUP BY report.id_reporte, {actor_name_column}, model.version, segment_model.version
            ORDER BY report.fecha_generacion DESC, report.id_reporte DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def _has_report_name_snapshot(self) -> bool:
        """Permite que la aplicación conviva con la base actual y el esquema limpio final."""
        return bool(self._session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'reporte_priorizacion'
                  AND column_name = 'nombre_usuario_generador'
            )
        """)).scalar_one())

    def get_saved_report(self, report_id: int) -> dict[str, Any] | None:
        """Reconstruye una exportación usando sus predicciones y snapshots históricos guardados."""
        header = self._session.execute(text("""
            SELECT report.id_reporte, report.semana, report.fecha_generacion, report.formato,
                   model.version AS modelo_version, capture.fecha_captura,
                   report.id_ejecucion, report.id_modelo_segmentacion,
                   segment_model.version AS segmentacion_version,
                   segment_model.resumen_clusters,
                   segment_model.silhouette_score AS segmentacion_silhouette
            FROM reporte_priorizacion report
            JOIN prediccion prediction ON prediction.id_reporte=report.id_reporte
            JOIN modelo_predictivo model ON model.id_modelo=prediction.id_modelo
            JOIN ejecucion_recoleccion capture ON capture.id_ejecucion=prediction.id_ejecucion
            LEFT JOIN modelo_segmentacion segment_model
              ON segment_model.id_modelo_segmentacion=report.id_modelo_segmentacion
            WHERE report.id_reporte=:report_id
            ORDER BY prediction.id_prediccion
            LIMIT 1
        """), {"report_id": report_id}).mappings().first()
        if header is None:
            return None

        rows = self._session.execute(text("""
            SELECT snapshot.id_mascota, snapshot.sku, snapshot.nombre, snapshot.especie,
                   snapshot.sexo, snapshot.edad_meses, snapshot.edad_estimada,
                   snapshot.tamano, snapshot.tamano_estimado,
                   snapshot.condicion_especial, snapshot.condicion_detalle,
                   snapshot.orden_publicacion, prediction.probabilidad_adopcion,
                   prediction.nivel_prioridad
            FROM prediccion prediction
            JOIN snapshot_catalogo snapshot
              ON snapshot.id_mascota=prediction.id_mascota
             AND snapshot.id_ejecucion=prediction.id_ejecucion
            WHERE prediction.id_reporte=:report_id
            ORDER BY CASE LOWER(prediction.nivel_prioridad)
                         WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baja' THEN 3 ELSE 4 END,
                     prediction.probabilidad_adopcion ASC,
                     snapshot.orden_publicacion DESC, snapshot.sku
        """), {"report_id": report_id}).mappings().all()
        if not rows:
            return None
        oe3_items: list[dict[str, Any]] = []
        if header["id_modelo_segmentacion"] is not None:
            oe3_rows = self._session.execute(text("""
                SELECT assignment.id_asignacion_segmento, assignment.numero_segmento,
                       assignment.criterios_desfavorecidos, snapshot.id_snapshot, snapshot.sku,
                       snapshot.nombre, snapshot.edad_meses, snapshot.edad_estimada,
                       snapshot.tamano, snapshot.tamano_estimado, snapshot.nivel_energia,
                       snapshot.condicion_especial, snapshot.condicion_detalle,
                       model.version, model.resumen_clusters
                FROM reporte_segmento_detalle report_segment
                JOIN asignacion_segmento assignment
                  ON assignment.id_asignacion_segmento=report_segment.id_asignacion_segmento
                JOIN snapshot_catalogo snapshot ON snapshot.id_snapshot=assignment.id_snapshot
                JOIN modelo_segmentacion model
                  ON model.id_modelo_segmentacion=assignment.id_modelo_segmentacion
                WHERE report_segment.id_reporte=:report_id
                ORDER BY assignment.numero_segmento, snapshot.sku
            """), {"report_id": report_id}).mappings().all()
            oe3_items = [dict(row) for row in oe3_rows]
        return {
            **dict(header), "items": [dict(row) for row in rows], "total": len(rows),
            "oe3_items": oe3_items,
        }

    def save_report(
        self,
        *,
        user_id: int,
        week: int,
        formato: str,
        model_id: int,
        run_id: int,
        items: list[dict[str, Any]],
        segmentation_model_id: int | None,
        segmentation_assignments: list[dict[str, Any]],
        generated_at: datetime,
    ) -> int:
        """Guarda la exportación y copia sus filas para que el reporte sea inmutable."""
        try:
            report_values = {
                "user_id": user_id, "week": week, "generated_at": generated_at, "format": formato,
                "run_id": run_id, "segment_model_id": segmentation_model_id,
            }
            if self._has_report_name_snapshot():
                report_id = self._session.execute(text("""
                    INSERT INTO reporte_priorizacion
                        (id_usuario, nombre_usuario_generador, semana, fecha_generacion, formato,
                         id_ejecucion, id_modelo_segmentacion)
                    SELECT account.id_usuario, account.nombre, :week, :generated_at, :format,
                           :run_id, :segment_model_id
                    FROM usuario account WHERE account.id_usuario = :user_id
                    RETURNING id_reporte
                """), report_values).scalar_one()
            else:
                report_id = self._session.execute(text("""
                    INSERT INTO reporte_priorizacion
                        (id_usuario, semana, fecha_generacion, formato, id_ejecucion, id_modelo_segmentacion)
                    VALUES (:user_id, :week, :generated_at, :format, :run_id, :segment_model_id)
                    RETURNING id_reporte
                """), report_values).scalar_one()

            for item in items:
                self._session.execute(text("""
                    INSERT INTO prediccion
                        (id_modelo, id_mascota, id_ejecucion, id_reporte,
                         probabilidad_adopcion, nivel_prioridad, fecha)
                    VALUES (:model_id, :pet_id, :run_id, :report_id,
                            :probability, :priority, :generated_at)
                """), {
                    "model_id": model_id,
                    "pet_id": item["id_mascota"],
                    "run_id": run_id,
                    "report_id": report_id,
                    "probability": item["probabilidad_adopcion"],
                    "priority": item["nivel_prioridad"],
                    "generated_at": generated_at,
                })
            for assignment in segmentation_assignments:
                self._session.execute(text("""
                    INSERT INTO reporte_segmento_detalle (id_reporte, id_asignacion_segmento)
                    VALUES (:report_id, :assignment_id)
                """), {"report_id": report_id, "assignment_id": assignment["id_asignacion_segmento"]})
            self._session.commit()
            return int(report_id)
        except Exception:
            self._session.rollback()
            raise
