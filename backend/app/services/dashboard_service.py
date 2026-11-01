"""Prepara el resumen y la evolución breve del Dashboard HU08."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.infrastructure.dashboard_repository import DashboardRepository


class DashboardService:
    """Combina métricas existentes sin volver a entrenar ni alterar módulos previos."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._repository = DashboardRepository(session)
        self._settings = settings

    def summary(self) -> dict[str, Any]:
        runs = self._repository.completed_runs(self._settings.dashboard_history_capture_limit)
        activity = self._repository.recent_activity(self._settings.dashboard_activity_limit)
        evolution = []
        for run in runs:
            evolution.append(self._capture_result(run))

        if not runs:
            return {
                "estado": "sin_capturas",
                "captura": None,
                "oe1": {"meta_aumento_porcentaje": self._settings.dashboard_oe1_target_increase_percent},
                "oe2": {
                    "alertas_altas_abiertas": self._repository.high_alert_count(),
                    "meta_exactitud_porcentaje": self._settings.dashboard_oe2_target_accuracy_percent,
                },
                "oe3": {
                    "meta_cobertura_porcentaje": self._settings.dashboard_oe3_target_coverage_percent,
                },
                "evolucion": [],
                "actividad": activity,
            }

        latest = runs[0]
        result = evolution[0]
        oe1 = result["oe1"]
        oe2 = {
            "alertas_altas_abiertas": self._repository.high_alert_count(),
            "meta_exactitud_porcentaje": self._settings.dashboard_oe2_target_accuracy_percent,
            "riesgo_alto_captura": result["oe2"],
        }
        oe3 = result["oe3"]
        oe1["meta_aumento_porcentaje"] = self._settings.dashboard_oe1_target_increase_percent
        oe3["meta_cobertura_porcentaje"] = self._settings.dashboard_oe3_target_coverage_percent
        return {
            "estado": "listo",
            "captura": latest,
            "catalogo": {
                "perfiles_total": int(latest["perfiles_total"]),
                "disponibles": int(latest["perfiles_disponibles"]),
                "no_disponibles": int(latest["perfiles_no_disponibles"]),
                "sin_publicar": int(latest["perfiles_sin_publicar"]),
                "prioridad_alta": oe1.get("prioridad_alta"),
                "prioridad_media": oe1.get("prioridad_media"),
                "prioridad_baja": oe1.get("prioridad_baja"),
                "alertas_altas_abiertas": oe2["alertas_altas_abiertas"],
            },
            "oe1": oe1,
            "oe2": oe2,
            "oe3": oe3,
            "evolucion": evolution,
            "actividad": activity,
        }

    def _capture_result(self, run: dict[str, Any]) -> dict[str, Any]:
        run_id = int(run["id_ejecucion"])
        disadvantaged = self._repository.disadvantaged_count(run_id)
        prediction = self._repository.adoption_metrics(run_id)
        consistency = self._repository.consistency_metrics(run_id)
        segmentation = self._repository.segmentation_metrics(run_id)
        eligible_assigned = int(segmentation["perfiles_desfavorecidos_asignados"]) if segmentation else 0
        coverage = round(eligible_assigned / disadvantaged * 100, 1) if disadvantaged else None
        oe1 = {
            "version": prediction["version"] if prediction else None,
            "predicciones": int(prediction["predicciones"]) if prediction else 0,
            "prioridad_alta": int(prediction["prioridad_alta"]) if prediction else 0,
            "prioridad_media": int(prediction["prioridad_media"]) if prediction else 0,
            "prioridad_baja": int(prediction["prioridad_baja"]) if prediction else 0,
        }
        oe3 = {
            "version": segmentation["version"] if segmentation else None,
            "segmentos": int(segmentation["segmentos"]) if segmentation else 0,
            "silhouette": segmentation["silhouette"] if segmentation else None,
            "perfiles_asignados": int(segmentation["perfiles_asignados"]) if segmentation else 0,
            "perfiles_con_criterios": disadvantaged,
            "perfiles_con_criterios_asignados": eligible_assigned,
            "cobertura_porcentaje": coverage,
        }
        return {
            "id_ejecucion": run_id,
            "fecha_captura": run["fecha_captura"],
            "semana": int(run["semana"]),
            "perfiles_total": int(run["perfiles_total"]),
            "perfiles_disponibles": int(run["perfiles_disponibles"]),
            "oe1": oe1,
            "oe2": {
                "version": consistency["version"] if consistency else None,
                "perfiles_evaluados": int(consistency["perfiles_evaluados"]) if consistency else 0,
                "riesgo_alto": int(consistency["riesgo_alto"]) if consistency else 0,
            },
            "oe3": oe3,
        }
