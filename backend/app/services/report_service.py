"""Casos de uso HU05: consultar la priorización vigente y exportar reportes."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.domain.disadvantaged_profiles import classify_profile
from app.infrastructure.report_exporter import export_pdf, export_xlsx
from app.infrastructure.report_repository import ReportRepository


class ReportServiceError(ValueError):
    """Error funcional seguro para una fuente de reporte no disponible."""


class ReportExportError(RuntimeError):
    """Fallo interno al preparar o registrar un archivo solicitado."""


class ReportNotFoundError(ValueError):
    """El reporte solicitado no existe o no conserva filas exportables."""


class ReportService:
    def __init__(self, session: Session) -> None:
        self._repository = ReportRepository(session)

    def current(self) -> dict[str, Any]:
        source = self._repository.get_current_source()
        if source["estado"] != "listo":
            return {"estado": source["estado"], "mensaje": source["mensaje"], "items": [], "total": 0}
        capture = source["captura"]
        counts = {"alta": 0, "media": 0, "baja": 0}
        items = []
        for row in source["items"]:
            priority = str(row["nivel_prioridad"]).casefold()
            counts[priority] += 1
            items.append(classify_profile({
                **row,
                "probabilidad_adopcion": float(row["probabilidad_adopcion"]),
                "nivel_prioridad": priority.capitalize(),
            }))
        oe3 = source["oe3"]
        oe3_summaries = oe3["modelo"]["resumen_clusters"] if oe3["modelo"] else []
        summary_by_id = {item["numero_segmento"]: item for item in oe3_summaries}
        oe3_items = []
        for row in oe3["items"]:
            cluster_summary = summary_by_id.get(int(row["numero_segmento"]), {})
            oe3_items.append({
                **row,
                "segmento_nombre": cluster_summary.get("nombre", f"Segmento {row['numero_segmento']}"),
                "segmento_resumen": cluster_summary,
            })
        return {
            "estado": "listo",
            "mensaje": None,
            "semana": capture["semana"],
            "fecha_captura": capture["fecha_captura"],
            "modelo_version": source["modelo"]["version"],
            "total": source["total"],
            "prioridades": counts,
            "items": items,
            "oe3": {
                "estado": oe3["estado"],
                "total": oe3["cantidad_perfiles_disponibles"],
                "total_desfavorecidos": oe3["cantidad_desfavorecida"],
                "modelo_version": oe3["modelo"]["version"] if oe3["modelo"] else None,
                "silhouette_score": float(oe3["modelo"]["silhouette_score"]) if oe3["modelo"] else None,
                "segmentos": oe3_summaries,
                "items": oe3_items,
            },
        }

    def history(self) -> list[dict[str, Any]]:
        """Devuelve las últimas exportaciones para consulta y descarga histórica."""
        return self._repository.get_report_history()

    def export(self, *, user_id: int, formato: str) -> tuple[bytes, str, str]:
        source = self._repository.get_current_source()
        if source["estado"] != "listo":
            raise ReportServiceError(source["mensaje"])
        generated_at = datetime.now(ZoneInfo("America/Lima")).replace(tzinfo=None)
        report = {**source, "captura": dict(source["captura"]), "modelo": dict(source["modelo"])}
        report["items"] = [classify_profile({
            **row,
            "nivel_prioridad": str(row["nivel_prioridad"]).capitalize(),
        }) for row in source["items"]]
        oe3 = source["oe3"]
        summaries = oe3["modelo"]["resumen_clusters"] if oe3["modelo"] else []
        summary_by_id = {item["numero_segmento"]: item for item in summaries}
        report["oe3"] = {
            "total": oe3["cantidad_perfiles_disponibles"],
            "total_desfavorecidos": oe3["cantidad_desfavorecida"],
            "modelo_version": oe3["modelo"]["version"] if oe3["modelo"] else None,
            "silhouette_score": (
                float(oe3["modelo"]["silhouette_score"])
                if oe3["modelo"] and oe3["estado"] == "listo" else None
            ),
            "items": [{
                **item,
                "segmento_nombre": summary_by_id.get(int(item["numero_segmento"]), {}).get(
                    "nombre", f"Segmento {item['numero_segmento']}"
                ),
                "segmento_resumen": summary_by_id.get(int(item["numero_segmento"]), {}),
            } for item in oe3["items"]] if oe3["estado"] == "listo" else [],
        }
        try:
            content = export_pdf(report, generated_at) if formato == "pdf" else export_xlsx(report, generated_at)
            report_id = self._repository.save_report(
                user_id=user_id,
                week=int(source["captura"]["semana"]),
                formato=formato,
                model_id=int(source["modelo"]["id_modelo"]),
                run_id=int(source["captura"]["id_ejecucion"]),
                items=source["items"],
                segmentation_model_id=(
                    int(source["oe3"]["modelo"]["id_modelo_segmentacion"])
                    if source["oe3"]["modelo"] and source["oe3"]["estado"] == "listo" else None
                ),
                segmentation_assignments=(
                    source["oe3"]["items"] if source["oe3"]["estado"] == "listo" else []
                ),
                generated_at=generated_at,
            )
        except Exception as exc:
            raise ReportExportError("No se pudo generar y registrar el archivo del reporte.") from exc
        filename = f"reporte_priorizacion_{formato}_{report_id}.{formato}"
        media_type = "application/pdf" if formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return content, filename, media_type

    def export_saved(self, report_id: int) -> tuple[bytes, str, str]:
        """Vuelve a generar el archivo desde el snapshot y predicciones originales del reporte."""
        saved = self._repository.get_saved_report(report_id)
        if saved is None:
            raise ReportNotFoundError("No se encontró el reporte solicitado.")
        report = {
            "captura": {"semana": saved["semana"], "fecha_captura": saved["fecha_captura"]},
            "modelo": {"version": saved["modelo_version"]},
            "items": [classify_profile({
                **item,
                "nivel_prioridad": str(item["nivel_prioridad"]).capitalize(),
            }) for item in saved["items"]],
        }
        cluster_summaries = saved.get("resumen_clusters") or []
        summary_by_id = {item["numero_segmento"]: item for item in cluster_summaries}
        saved_oe3_items = saved.get("oe3_items", [])
        report["oe3"] = {
            "total": len(saved_oe3_items),
            "total_desfavorecidos": sum(
                bool(item.get("criterios_desfavorecidos")) for item in saved_oe3_items
            ),
            "modelo_version": saved.get("segmentacion_version"),
            "silhouette_score": (
                float(saved["segmentacion_silhouette"])
                if saved.get("segmentacion_silhouette") is not None else None
            ),
            "items": [{
                **item,
                "segmento_nombre": summary_by_id.get(int(item["numero_segmento"]), {}).get(
                    "nombre", f"Segmento {item['numero_segmento']}"
                ),
                "segmento_resumen": summary_by_id.get(int(item["numero_segmento"]), {}),
            } for item in saved_oe3_items],
        }
        try:
            formato = str(saved["formato"]).casefold()
            generated_at = saved["fecha_generacion"]
            content = export_pdf(report, generated_at) if formato == "pdf" else export_xlsx(report, generated_at)
        except Exception as exc:
            raise ReportExportError("No se pudo volver a generar el archivo del reporte.") from exc
        filename = f"reporte_priorizacion_{formato}_{report_id}.{formato}"
        media_type = "application/pdf" if formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return content, filename, media_type
