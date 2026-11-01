"""Casos de uso para crear, activar y actualizar los segmentos OE3."""

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.profile_clustering import (
    ProfileClusteringError,
    prepare_profile_features,
    project_profile_clusters,
    select_disadvantaged_profiles,
    train_profile_clusters,
)
from app.infrastructure.model_artifact_storage import ModelArtifactError, ModelArtifactStorage
from app.infrastructure.segmentation_repository import SegmentationRepository


class SegmentationServiceError(ValueError):
    """Solicitud válida que no puede completarse con la captura o modelo disponible."""


class SegmentationService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._repository = SegmentationRepository(session)
        self._settings = settings
        # Directorio independiente para no sobrescribir artefactos de Random Forest o HU04.
        self._storage = ModelArtifactStorage(Path(settings.model_artifact_dir) / "segmentation")

    def options(self) -> dict[str, Any]:
        source = self._repository.latest_available_profiles()
        if source is None:
            return {
                "estado": "sin_capturas", "captura": None,
                "perfiles_disponibles": 0, "perfiles_elegibles": 0,
                "segmentos_permitidos": [],
            }
        eligible = select_disadvantaged_profiles(source["items"])
        # Mantiene tres perfiles por segmento y respeta el mínimo operativo de diez.
        allowed_clusters = [
            count for count in range(2, 6)
            if len(eligible) >= max(10, count * 3)
        ]
        return {
            "estado": "listo" if allowed_clusters else "sin_perfiles_suficientes",
            "captura": source["captura"],
            "perfiles_disponibles": len(source["items"]),
            "perfiles_elegibles": len(eligible),
            "segmentos_permitidos": allowed_clusters,
        }

    def train(self, *, user_id: int, cluster_count: int) -> dict[str, Any]:
        source = self._repository.latest_available_profiles()
        if source is None:
            raise SegmentationServiceError("Importa una captura completa antes de entrenar K-Means.")
        try:
            result = train_profile_clusters(
                source["items"],
                cluster_count=cluster_count,
                seed=self._settings.segmentation_random_seed,
                n_init=self._settings.segmentation_n_init,
            )
            model = self._repository.create_candidate(
                user_id=user_id,
                run_id=int(source["captura"]["id_ejecucion"]),
                result=result,
                estimator=result["estimator"],
                storage=self._storage,
                trained_at=datetime.now(ZoneInfo("America/Lima")).replace(tzinfo=None),
            )
        except ProfileClusteringError as exc:
            raise SegmentationServiceError(str(exc)) from exc
        except Exception as exc:
            raise SegmentationServiceError("No se pudo guardar el modelo de segmentación.") from exc
        return self._public_model(model)

    def activate(self, model_id: int) -> dict[str, Any]:
        model = self._repository.get_model(model_id)
        if model is None or model["estado"] != "candidato":
            raise SegmentationServiceError("No se encontró un candidato disponible para activar.")
        return self._apply_model(model, activate=True)

    def refresh(self) -> dict[str, Any]:
        models = [item for item in self._repository.list_models() if item["es_vigente"]]
        if not models:
            raise SegmentationServiceError("Primero activa un modelo K-Means.")
        model = self._repository.get_model(int(models[0]["id_modelo_segmentacion"]))
        assert model is not None
        return self._apply_model(model, activate=False)

    def list_models(self) -> list[dict[str, Any]]:
        return [self._public_model(item) for item in self._repository.list_models()]

    def scatter_plot(self, model_id: int) -> dict[str, Any]:
        """Prepara puntos del modelo solicitado usando su captura original."""
        model = self._repository.get_model(model_id)
        if model is None:
            raise SegmentationServiceError("No se encontró la versión de K-Means solicitada.")
        profiles = self._repository.available_profiles_for_run(
            int(model["id_ejecucion_referencia"])
        )
        try:
            estimator = self._storage.load(model["artefacto_ruta"], model["artefacto_sha256"])
            projection = project_profile_clusters(estimator, profiles)
        except ModelArtifactError as exc:
            raise SegmentationServiceError("No se pudo validar el artefacto de esta versión.") from exc
        except ProfileClusteringError as exc:
            raise SegmentationServiceError(str(exc)) from exc
        except Exception as exc:
            raise SegmentationServiceError("No se pudo preparar el gráfico de segmentación.") from exc
        return {
            "id_modelo_segmentacion": int(model["id_modelo_segmentacion"]),
            "version": model["version"],
            "semana_referencia": int(model["semana_referencia"]),
            **projection,
        }

    def _apply_model(self, model: dict[str, Any], *, activate: bool) -> dict[str, Any]:
        source = self._repository.latest_available_profiles()
        if source is None:
            raise SegmentationServiceError("No hay una captura completa disponible.")
        eligible = select_disadvantaged_profiles(source["items"])
        if not eligible:
            raise SegmentationServiceError(
                "La última captura no contiene perfiles que cumplan los criterios HU06."
            )
        try:
            estimator = self._storage.load(model["artefacto_ruta"], model["artefacto_sha256"])
            # Reusa exactamente la normalización aplicada al entrenamiento, también con vacíos.
            frame = prepare_profile_features(eligible)
            labels = estimator.predict(frame).astype(int).tolist()
        except ModelArtifactError as exc:
            raise SegmentationServiceError("No se pudo validar el archivo del modelo de segmentación.") from exc
        except Exception as exc:
            raise SegmentationServiceError("No se pudieron asignar segmentos a la última captura.") from exc

        assignments = []
        for profile, zero_based_cluster in zip(eligible, labels, strict=True):
            assignments.append({
                **profile,
                "numero_segmento": zero_based_cluster + 1,
            })
        assigned_at = datetime.now(ZoneInfo("America/Lima")).replace(tzinfo=None)
        if activate:
            self._repository.activate_with_assignments(
                int(model["id_modelo_segmentacion"]), assignments, assigned_at
            )
        else:
            self._repository.refresh_assignments(
                int(model["id_modelo_segmentacion"]), assignments, assigned_at
            )
        return {
            **self._public_model(model),
            "estado": "vigente",
            "asignaciones_actualizadas": len(assignments),
            "semana_aplicada": source["captura"]["semana"],
        }

    @staticmethod
    def _public_model(model: dict[str, Any]) -> dict[str, Any]:
        """Limita la respuesta API a metadatos; nunca expone el objeto serializado."""
        return {
            "id_modelo_segmentacion": int(model["id_modelo_segmentacion"]),
            "version": model["version"],
            "algoritmo": model.get("algoritmo", "KMeans"),
            "cantidad_clusters": int(model["cantidad_clusters"]),
            "cantidad_perfiles": int(model["cantidad_perfiles"]),
            "silhouette_score": float(model["silhouette_score"]),
            "inertia": float(model["inertia"]),
            "variables": model["variables"],
            "resumen_clusters": model["resumen_clusters"],
            "parametros": model["parametros"],
            "estado": model["estado"],
            "es_vigente": bool(model["es_vigente"]),
            "fecha_entrenamiento": model["fecha_entrenamiento"],
            "semana_referencia": model.get("semana_referencia"),
            "fecha_captura_referencia": model.get("fecha_captura_referencia"),
        }
