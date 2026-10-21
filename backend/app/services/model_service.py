"""Casos de uso HU03: entrenar, consultar y activar el modelo predictivo."""

from pathlib import Path
from typing import Any

# pandas conserva los nombres de columnas para que el pipeline reutilice su preprocesamiento.
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.model_training import FEATURE_COLUMNS, ModelTrainingError, train_random_forest
from app.infrastructure.model_artifact_storage import ModelArtifactStorage
from app.infrastructure.model_repository import ModelRepository


class ModelServiceError(ValueError):
    """Error funcional seguro para devolver al Analista."""


class ModelService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._repository = ModelRepository(session)
        self._settings = settings
        self._artifacts = ModelArtifactStorage(Path(settings.model_artifact_dir))

    def options(self) -> dict[str, Any]:
        return {
            "datasets": self._repository.list_dataset_options(),
            "defaults": {
                "test_size": self._settings.model_default_test_size,
                "n_estimators": self._settings.model_default_estimators,
                "max_depth": None,
                "min_accuracy": self._settings.model_min_accuracy,
                "random_state": self._settings.model_random_seed,
                "priority_high_max": self._settings.model_priority_high_max,
                "priority_medium_max": self._settings.model_priority_medium_max,
            },
        }

    def train(
        self, dataset_id: int, test_size: float, n_estimators: int, max_depth: int | None,
    ) -> dict[str, Any]:
        rows = self._repository.get_training_rows(dataset_id)
        if rows is None:
            raise ModelServiceError("El dataset seleccionado no existe.")
        try:
            result = train_random_forest(
                rows,
                test_size=test_size,
                n_estimators=n_estimators,
                max_depth=max_depth,
                seed=self._settings.model_random_seed,
            )
            model_id = self._repository.save_candidate(
                dataset_id, result, self._settings.model_min_accuracy, self._artifacts
            )
        except ModelTrainingError as exc:
            raise ModelServiceError(str(exc)) from exc
        except Exception as exc:
            raise ModelServiceError("No se pudo guardar el resultado y artefacto del entrenamiento.") from exc
        model = self._repository.get_model(model_id)
        return self._public_model(model) if model else {"id_modelo": model_id}

    def list_models(self) -> list[dict[str, Any]]:
        return [self._public_model(model) for model in self._repository.list_models()]

    def catalog_predictions(self) -> dict[str, Any]:
        return self._repository.get_catalog_predictions()

    def activate(self, model_id: int) -> dict[str, Any]:
        model = self._repository.get_model(model_id)
        if model is None:
            raise ModelServiceError("No se encontró el modelo solicitado.")
        if model["estado"] != "publicable":
            raise ModelServiceError("Solo se pueden publicar modelos que superaron el umbral de Accuracy.")
        if not model["artefacto_ruta"] or not model["artefacto_sha256"]:
            raise ModelServiceError("El modelo no tiene un artefacto completo para publicar.")
        try:
            pipeline = self._artifacts.load(model["artefacto_ruta"], model["artefacto_sha256"])
        except Exception as exc:
            raise ModelServiceError("No se pudo verificar el archivo del modelo; no fue publicado.") from exc

        predictions = self._predict_latest_capture(pipeline)
        try:
            self._repository.activate_model(model_id, predictions)
        except (LookupError, ValueError) as exc:
            raise ModelServiceError(str(exc)) from exc
        except Exception as exc:
            raise ModelServiceError("No se pudo activar el modelo y guardar sus predicciones.") from exc
        activated = self._repository.get_model(model_id)
        response = self._public_model(activated) if activated else {"id_modelo": model_id}
        response["predicciones_generadas"] = len(predictions)
        return response

    def refresh_predictions(self, model_id: int) -> dict[str, Any]:
        """Vuelve a predecir la captura reciente conservando la versión vigente."""
        model = self._repository.get_model(model_id)
        if model is None or not model["es_vigente"]:
            raise ModelServiceError("Solo se pueden actualizar predicciones del modelo vigente.")
        if not model["artefacto_ruta"] or not model["artefacto_sha256"]:
            raise ModelServiceError("El modelo vigente no tiene un artefacto verificable.")
        try:
            pipeline = self._artifacts.load(model["artefacto_ruta"], model["artefacto_sha256"])
            predictions = self._predict_latest_capture(pipeline)
            self._repository.refresh_predictions(model_id, predictions)
        except ValueError as exc:
            raise ModelServiceError(str(exc)) from exc
        except Exception as exc:
            raise ModelServiceError("No se pudieron actualizar las predicciones del catálogo.") from exc
        return {"predicciones_generadas": len(predictions), "version": model["version"]}

    def _predict_latest_capture(self, pipeline: Any) -> list[dict[str, Any]]:
        """Calcula probabilidades para las mascotas disponibles del último snapshot completo."""
        pets = self._repository.get_available_pets()
        if not pets:
            return []
        features = pd.DataFrame(pets)[FEATURE_COLUMNS]
        probabilities = pipeline.predict_proba(features)
        positive_index = list(pipeline.named_steps["classifier"].classes_).index(1)
        predictions: list[dict[str, Any]] = []
        for pet, probability_row in zip(pets, probabilities, strict=True):
            # La clase positiva es salida del catálogo, usada como indicador indirecto de adopción.
            probability = float(probability_row[positive_index])
            if probability <= self._settings.model_priority_high_max:
                priority = "Alta"
            elif probability <= self._settings.model_priority_medium_max:
                priority = "Media"
            else:
                priority = "Baja"
            predictions.append({
                "id_ejecucion": pet["id_ejecucion"],
                "id_mascota": pet["id_mascota"],
                "probability": probability,
                "priority": priority,
            })
        return predictions

    @staticmethod
    def _public_model(model: dict[str, Any]) -> dict[str, Any]:
        """Expone métricas y explicación sin revelar rutas locales del artefacto."""
        return {
            key: model[key] for key in (
                "id_modelo", "version", "algoritmo", "estado", "es_vigente", "id_dataset",
                "dataset_version", "accuracy_score", "precision_score", "recall_score",
                "f1_score", "fecha_entrenamiento", "nro_registros_entrenamiento",
                "nro_registros_prueba", "nro_registros_excluidos", "umbral_accuracy",
                "clase_positiva", "matriz_confusion", "importancia_variables",
                "metadatos_entrenamiento",
            ) if key in model
        }
