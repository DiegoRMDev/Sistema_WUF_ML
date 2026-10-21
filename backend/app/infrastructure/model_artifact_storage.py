"""Almacenamiento privado e íntegro de modelos entrenados por el backend."""

import hashlib
import os
import tempfile
from pathlib import Path

# joblib conserva y recupera juntos los pasos de limpieza y el modelo ya entrenado.
import joblib


class ModelArtifactError(RuntimeError):
    """El archivo interno del modelo no está disponible o no conserva su integridad."""


class ModelArtifactStorage:
    def __init__(self, directory: Path) -> None:
        self._directory = directory.expanduser().resolve()

    def save(self, model_id: int, pipeline: object) -> tuple[str, str]:
        """Guarda un artefacto del backend y devuelve nombre e identificador SHA-256."""
        self._directory.mkdir(parents=True, exist_ok=True)
        filename = f"modelo_{model_id}.joblib"
        destination = self._directory / filename
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self._directory, suffix=".tmp", delete=False) as handle:
                temporary_name = handle.name
            # Joblib mantiene juntos el preprocesamiento y el estimador ya entrenado.
            joblib.dump(pipeline, temporary_name, compress=3)
            os.replace(temporary_name, destination)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            return filename, digest
        except Exception:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def load(self, filename: str, expected_digest: str) -> object:
        """Carga solo un archivo del directorio interno cuyo contenido conserva el hash."""
        # El nombre simple impide usar metadatos de la base para salir de la carpeta privada.
        if Path(filename).name != filename or not filename.endswith(".joblib"):
            raise ModelArtifactError("La referencia del artefacto no es válida.")
        path = self._directory / filename
        if not path.is_file():
            raise ModelArtifactError("No se encontró el artefacto entrenado.")
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise ModelArtifactError("El artefacto no supera la validación de integridad.")
        # joblib puede ejecutar código al deserializar; esta ruta solo admite artefactos internos.
        return joblib.load(path)

    def delete(self, filename: str | None) -> None:
        if filename and Path(filename).name == filename:
            (self._directory / filename).unlink(missing_ok=True)
