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
                   pet.edad_meses, pet.edad_estimada, pet.tamano,
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

        return {
            "estado": "listo",
            "captura": dict(run),
            "modelo": dict(model),
            "items": [dict(row) for row in rows],
            "total": available_count,
        }

    def get_report_history(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """Lista exportaciones guardadas que tienen sus filas de predicción asociadas."""
        rows = self._session.execute(text("""
            SELECT report.id_reporte, report.semana, report.fecha_generacion, report.formato,
                   account.nombre AS usuario,
                   model.version AS modelo_version,
                   COUNT(prediction.id_prediccion) AS total
            FROM reporte_priorizacion report
            JOIN usuario account ON account.id_usuario=report.id_usuario
            JOIN prediccion prediction ON prediction.id_reporte=report.id_reporte
            JOIN modelo_predictivo model ON model.id_modelo=prediction.id_modelo
            GROUP BY report.id_reporte, account.nombre, model.version
            ORDER BY report.fecha_generacion DESC, report.id_reporte DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_saved_report(self, report_id: int) -> dict[str, Any] | None:
        """Reconstruye una exportación usando sus predicciones y snapshots históricos guardados."""
        header = self._session.execute(text("""
            SELECT report.id_reporte, report.semana, report.fecha_generacion, report.formato,
                   model.version AS modelo_version, capture.fecha_captura
            FROM reporte_priorizacion report
            JOIN prediccion prediction ON prediction.id_reporte=report.id_reporte
            JOIN modelo_predictivo model ON model.id_modelo=prediction.id_modelo
            JOIN ejecucion_recoleccion capture ON capture.id_ejecucion=prediction.id_ejecucion
            WHERE report.id_reporte=:report_id
            ORDER BY prediction.id_prediccion
            LIMIT 1
        """), {"report_id": report_id}).mappings().first()
        if header is None:
            return None

        rows = self._session.execute(text("""
            SELECT snapshot.id_mascota, snapshot.sku, snapshot.nombre, snapshot.especie,
                   snapshot.sexo, snapshot.edad_meses, snapshot.edad_estimada, snapshot.tamano,
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
        return {**dict(header), "items": [dict(row) for row in rows], "total": len(rows)}

    def save_report(
        self,
        *,
        user_id: int,
        week: int,
        formato: str,
        model_id: int,
        run_id: int,
        items: list[dict[str, Any]],
        generated_at: datetime,
    ) -> int:
        """Guarda la exportación y copia sus filas para que el reporte sea inmutable."""
        try:
            report_id = self._session.execute(text("""
                INSERT INTO reporte_priorizacion (id_usuario, semana, fecha_generacion, formato)
                VALUES (:user_id, :week, :generated_at, :format)
                RETURNING id_reporte
            """), {
                "user_id": user_id, "week": week, "generated_at": generated_at, "format": formato,
            }).scalar_one()

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
            self._session.commit()
            return int(report_id)
        except Exception:
            self._session.rollback()
            raise
