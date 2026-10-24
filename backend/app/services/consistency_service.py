"""Casos de uso HU04: entrenar y aplicar el árbol demo de consistencia."""

import json
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.consistency_training import (
    ConsistencyTrainingError,
    build_proxy_samples,
    explain_prediction,
    explain_review_priority,
    export_tree_diagram,
    predict_risk,
    review_priority,
    train_decision_tree,
)
from app.infrastructure.consistency_repository import ConsistencyRepository
from app.infrastructure.model_artifact_storage import ModelArtifactStorage

logger = logging.getLogger(__name__)


class ConsistencyServiceError(ValueError):
    """Error de negocio que impide evaluar la consistencia del catálogo."""


class ConsistencyService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repository = ConsistencyRepository(session)
        # Mantiene los árboles HU04 en su propia subcarpeta privada y evita colisiones con HU03.
        self._artifacts = ModelArtifactStorage(settings.model_artifact_dir / "consistency")

    def train_and_evaluate(
        self,
        actor_id: int,
        *,
        max_depth: int | None = None,
        test_size: float | None = None,
    ) -> dict[str, Any]:
        """Entrena el árbol, aplica la regla acordada y mide cuánto coincide el árbol."""
        latest_run = self._repository.latest_completed_run()
        if latest_run is None:
            raise ConsistencyServiceError("Primero importa una captura completa del catálogo.")

        timeline = self._repository.training_timeline()
        capture_count = len({int(row["id_ejecucion"]) for row in timeline})
        if capture_count < 3:
            raise ConsistencyServiceError("Se requieren al menos tres capturas completas para entrenar el árbol HU04.")
        samples = build_proxy_samples(
            timeline,
            high_min_captures=self._settings.consistency_high_min_captures,
            high_min_age_days=self._settings.consistency_high_min_age_days,
            medium_min_captures=self._settings.consistency_medium_min_captures,
            medium_min_age_days=self._settings.consistency_medium_min_age_days,
            max_capture_gap_days=self._settings.consistency_max_capture_gap_days,
        )
        try:
            trained = train_decision_tree(
                samples,
                test_size=test_size if test_size is not None else self._settings.consistency_test_size,
                random_seed=self._settings.consistency_random_seed,
                max_depth=max_depth if max_depth is not None else self._settings.consistency_max_depth,
            )
        except ConsistencyTrainingError as exc:
            raise ConsistencyServiceError(str(exc)) from exc

        latest_samples = [
            sample for sample in samples
            if int(sample["id_ejecucion"]) == int(latest_run["id_ejecucion"])
        ]
        if not latest_samples:
            raise ConsistencyServiceError("La última captura no contiene perfiles disponibles para evaluar.")

        assessments: list[dict[str, Any]] = []
        for sample in latest_samples:
            features = {name: sample[name] for name in (
                "dias_publicacion", "capturas_disponible", "capturas_observadas"
            )}
            # El árbol es una aproximación visible; la regla exacta fija la prioridad operativa.
            priority = review_priority(
                features,
                high_min_captures=self._settings.consistency_high_min_captures,
                high_min_age_days=self._settings.consistency_high_min_age_days,
                medium_min_captures=self._settings.consistency_medium_min_captures,
                medium_min_age_days=self._settings.consistency_medium_min_age_days,
            )
            tree_prediction = predict_risk(trained.estimator, features)
            assessments.append({
                "id_mascota": int(sample["id_mascota"]),
                "id_snapshot": int(sample["id_snapshot"]),
                "sku": str(sample["sku"]),
                "nombre": str(sample["nombre"]),
                "nivel_riesgo": priority,
                "justificacion": explain_review_priority(
                    priority,
                    features,
                    high_min_captures=self._settings.consistency_high_min_captures,
                    high_min_age_days=self._settings.consistency_high_min_age_days,
                    medium_min_captures=self._settings.consistency_medium_min_captures,
                    medium_min_age_days=self._settings.consistency_medium_min_age_days,
                ),
                "indicadores": {
                    **features,
                    "origen": "prioridad_revision_hu04_v2",
                    "fuente_prioridad": "regla_directa_hu04_v2",
                    "prediccion_arbol": tree_prediction,
                    "coincide_arbol_regla": tree_prediction == priority,
                    "explicacion_arbol": explain_prediction(trained.estimator, features),
                    "limites_regla": {
                        "alto_capturas": self._settings.consistency_high_min_captures,
                        "alto_antiguedad_dias": self._settings.consistency_high_min_age_days,
                        "medio_capturas": self._settings.consistency_medium_min_captures,
                        "medio_antiguedad_dias": self._settings.consistency_medium_min_age_days,
                        "intervalo_maximo_capturas_dias": self._settings.consistency_max_capture_gap_days,
                    },
                },
            })

        metadata = {
            "nro_registros_entrenamiento": trained.train_count,
            "nro_registros_prueba": trained.test_count,
            "conteo_clases_proxy": trained.class_counts,
            "parametros": trained.parameters,
            "diagrama_arbol": trained.tree_diagram,
            "capturas_completas": capture_count,
            "intervalo_maximo_capturas_dias": self._settings.consistency_max_capture_gap_days,
            "version_regla_revision": "prioridad_revision_hu04_v2",
            "fuente_prioridad_catalogo": "regla_directa_hu04_v2",
            "comparacion_arbol_regla_catalogo": {
                "total": len(assessments),
                "coincidencias": sum(
                    item["indicadores"]["coincide_arbol_regla"] for item in assessments
                ),
                "diferencias": sum(
                    not item["indicadores"]["coincide_arbol_regla"] for item in assessments
                ),
            },
            "umbrales_etiquetado_demo": {
                "alto_min_capturas_disponible": self._settings.consistency_high_min_captures,
                "alto_min_antiguedad_dias": self._settings.consistency_high_min_age_days,
                "medio_min_capturas_disponible": self._settings.consistency_medium_min_captures,
                "medio_min_antiguedad_dias": self._settings.consistency_medium_min_age_days,
            },
            "advertencia": (
                "Etiquetas provisionales derivadas de reglas; las métricas no validan estados reales."
            ),
        }

        filename: str | None = None
        try:
            model_id, _version = self._repository.insert_model(
                actor_id=actor_id,
                execution_id=int(latest_run["id_ejecucion"]),
                metrics=trained.metrics,
                confusion=trained.confusion,
                importance=trained.feature_importance,
                metadata=metadata,
                rules=trained.tree_rules,
            )
            filename, digest = self._artifacts.save(model_id, trained.estimator)
            self._repository.set_artifact_reference(model_id, filename, digest)
            self._repository.insert_assessments(
                model_id=model_id,
                execution_id=int(latest_run["id_ejecucion"]),
                captured_on=_to_date(latest_run["fecha_captura"]),
                assessments=assessments,
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            if filename:
                self._artifacts.delete(filename)
            logger.exception("No se pudo persistir la evaluación HU04; actor_id=%s", actor_id)
            raise

        report = self._repository.latest_report()
        if report is None:
            raise ConsistencyServiceError("No se pudo recuperar el resultado de la evaluación.")
        self._attach_tree_diagram(report)
        report["history"] = self._repository.model_history()
        return _json_safe(report)

    def latest_report(self) -> dict[str, Any]:
        report = self._repository.latest_report()
        if report is None:
            return {
                "model": None, "items": [], "history": [],
                "message": "Todavía no se ha evaluado la consistencia.",
            }
        self._attach_tree_diagram(report)
        report["history"] = self._repository.model_history()
        return _json_safe(report)

    def version_report(self, model_id: int) -> dict[str, Any]:
        report = self._repository.report_for_model(model_id)
        if report is None:
            raise ConsistencyServiceError("No se encontró esa versión del árbol.")
        self._attach_tree_diagram(report)
        report["history"] = self._repository.model_history()
        return _json_safe(report)

    def _attach_tree_diagram(self, report: dict[str, Any]) -> None:
        """Completa el diagrama desde el artefacto para versiones entrenadas antes de esta mejora."""
        metadata = report.get("metadatos_entrenamiento") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not metadata.get("diagrama_arbol"):
            try:
                estimator = self._artifacts.load(
                    str(report["artefacto_ruta"]), str(report["artefacto_sha256"])
                )
                metadata["diagrama_arbol"] = export_tree_diagram(estimator)
            except Exception:
                # Las métricas e historial siguen disponibles aunque falte un artefacto antiguo.
                logger.warning(
                    "No se pudo reconstruir el diagrama del árbol; model_id=%s",
                    report.get("id_modelo_consistencia"),
                    exc_info=True,
                )
        report["metadatos_entrenamiento"] = metadata
        # La ruta interna y el hash no se envían al navegador.
        report.pop("artefacto_ruta", None)
        report.pop("artefacto_sha256", None)


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _json_safe(report: dict[str, Any]) -> dict[str, Any]:
    """Normaliza JSONB, fechas y decimales para responder de forma estable desde la API."""
    model = {
        key: value for key, value in report.items()
        if key not in {"items", "history", "id_modelo_consistencia", "id_ejecucion_referencia"}
    }
    model["id_modelo_consistencia"] = int(report["id_modelo_consistencia"])
    model["id_ejecucion_referencia"] = int(report["id_ejecucion_referencia"])
    model["accuracy_score"] = float(report["accuracy_score"])
    model["f1_macro_score"] = float(report["f1_macro_score"])
    trained_at = _to_datetime(report["fecha_entrenamiento"])
    model["fecha_entrenamiento"] = (
        trained_at.replace(tzinfo=ZoneInfo("America/Lima"))
        if trained_at.tzinfo is None else trained_at.astimezone(ZoneInfo("America/Lima"))
    ).isoformat()
    if isinstance(model.get("matriz_confusion"), str):
        model["matriz_confusion"] = json.loads(model["matriz_confusion"])
    if isinstance(model.get("importancia_variables"), str):
        model["importancia_variables"] = json.loads(model["importancia_variables"])
    if isinstance(model.get("metadatos_entrenamiento"), str):
        model["metadatos_entrenamiento"] = json.loads(model["metadatos_entrenamiento"])
    items = []
    for row in report.get("items", []):
        item = dict(row)
        item["fecha_evaluacion"] = _to_date(item["fecha_evaluacion"]).isoformat()
        item["id_mascota"] = int(item["id_mascota"])
        if isinstance(item.get("indicadores"), str):
            item["indicadores"] = json.loads(item["indicadores"])
        items.append(item)
    history = []
    for row in report.get("history", []):
        entry = dict(row)
        entry["id_modelo_consistencia"] = int(entry["id_modelo_consistencia"])
        entry["id_ejecucion_referencia"] = int(entry["id_ejecucion_referencia"])
        entry["accuracy_score"] = float(entry["accuracy_score"])
        entry["f1_macro_score"] = float(entry["f1_macro_score"])
        entry["fecha_entrenamiento"] = (
            _to_datetime(entry["fecha_entrenamiento"])
            .replace(tzinfo=ZoneInfo("America/Lima")).isoformat()
        )
        history.append(entry)
    return {"model": model, "items": items, "history": history, "message": None}


def _to_datetime(value: datetime | date | str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return datetime.fromisoformat(str(value))
