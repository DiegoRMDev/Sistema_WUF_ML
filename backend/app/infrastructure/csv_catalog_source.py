"""Lee, valida y convierte una captura CSV en perfiles del dominio HU01."""

import csv
import io
from collections import Counter
from datetime import date
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import Settings
from app.domain.catalog import (
    CatalogAlreadyImported,
    CatalogBatch,
    CatalogPet,
    CatalogSourceError,
)

_REQUIRED_COLUMNS = {
    "sku", "nombre", "especie", "raza", "sexo", "edad_meses", "edad_estimada",
    "tipo_pelaje", "tamano", "tamano_estimado", "nivel_energia", "condicion_especial",
    "condicion_detalle", "descripcion", "orden_publicacion", "estado_publicado",
    "fecha_publicacion", "url_perfil", "etiquetas", "etiqueta_adoptado",
}


class _CsvPet(BaseModel):
    """Contrato del CSV: tipos y límites coinciden con las columnas de mascota/snapshot."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sku: str = Field(min_length=1, max_length=10)
    nombre: str = Field(min_length=1, max_length=80)
    especie: str = Field(min_length=1, max_length=10)
    raza: str = Field(min_length=1, max_length=30)
    sexo: str
    edad_meses: int | None = Field(ge=0)
    edad_estimada: bool
    tipo_pelaje: str = Field(min_length=1, max_length=15)
    tamano: str = Field(min_length=1, max_length=10)
    tamano_estimado: bool
    nivel_energia: str = Field(min_length=1, max_length=10)
    condicion_especial: bool
    condicion_detalle: str | None = Field(max_length=200)
    descripcion: str | None = Field(max_length=512)
    orden_publicacion: int = Field(gt=0)
    estado_publicado: str
    fecha_publicacion: date
    url_perfil: str = Field(min_length=1, max_length=255)
    etiquetas: str = ""
    etiqueta_adoptado: bool

    @field_validator("etiquetas")
    @classmethod
    def validate_labels(cls, value: str) -> str:
        for label in (part.strip() for part in value.split("|")):
            if len(label) > 30:
                raise ValueError("cada etiqueta debe tener máximo 30 caracteres")
        return value

    @field_validator("especie")
    @classmethod
    def validate_species(cls, value: str) -> str:
        value = value.casefold()
        if value not in {"perro", "gato"}:
            raise ValueError("especie debe ser perro o gato")
        return value

    @field_validator("sexo")
    @classmethod
    def normalize_sex(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized in {"m", "macho", "masculino"}:
            return "M"
        if normalized in {"h", "f", "hembra", "femenino"}:
            return "H"
        raise ValueError("sexo debe ser M o H")

    @field_validator("estado_publicado")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        normalized = value.casefold().strip().replace(" ", "_")
        if normalized not in {"disponible", "no_disponible", "sin_publicar"}:
            raise ValueError("estado_publicado no reconocido")
        return normalized

    @field_validator("url_perfil")
    @classmethod
    def validate_profile_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"wuf.pe", "www.wuf.pe"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
        ):
            raise ValueError("url_perfil debe usar HTTPS y el dominio wuf.pe")
        return value


class CsvCatalogSource:
    """Valida un único CSV recibido en la solicitud de importación manual."""

    source_name = "csv_simulada"

    def __init__(
        self,
        settings: Settings,
        filename: str,
        content: bytes,
        used_references: set[str],
    ) -> None:
        # El nombre nunca se usa como ruta; solo se conserva para trazabilidad de la ejecución.
        safe_name = (filename or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
        if not safe_name or len(safe_name) > 255 or not safe_name.casefold().endswith(".csv"):
            raise CatalogSourceError("Selecciona un archivo con extensión .csv y un nombre válido.")
        if safe_name in used_references:
            raise CatalogAlreadyImported("Este nombre de archivo ya fue importado correctamente.")
        self._max_bytes = settings.catalog_csv_max_bytes
        if len(content) > self._max_bytes:
            raise CatalogSourceError("El archivo CSV excede el tamaño máximo configurado.")
        self._content = content
        self.source_reference = safe_name

    def fetch_pets(self) -> CatalogBatch:
        try:
            reader = csv.DictReader(io.StringIO(self._content.decode("utf-8-sig", errors="strict")))
            header_list = reader.fieldnames or []
            headers = set(header_list)
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise CatalogSourceError("El CSV debe tener encabezados y codificación UTF-8.") from exc
        if headers != _REQUIRED_COLUMNS or len(header_list) != len(headers):
            missing = sorted(_REQUIRED_COLUMNS - headers)
            extra = sorted(headers - _REQUIRED_COLUMNS)
            raise CatalogSourceError(
                f"Encabezados CSV inválidos; faltan {missing or 'ninguno'}; sobran {extra or 'ninguno'}."
            )

        pets: list[CatalogPet] = []
        rejected: Counter[str] = Counter()
        rejected_rows = 0
        counts = {"disponible": 0, "no_disponible": 0, "sin_publicar": 0}
        seen_skus: set[str] = set()
        for row in rows:
            try:
                values = self._convert_row(row)
                profile = _CsvPet.model_validate(values)
                if profile.sku in seen_skus:
                    rejected["sku_duplicado"] += 1
                    rejected_rows += 1
                    continue
                seen_skus.add(profile.sku)
                labels = tuple(dict.fromkeys(label.strip() for label in profile.etiquetas.split("|") if label.strip()))
                pets.append(
                    CatalogPet(
                        **profile.model_dump(exclude={"etiquetas", "etiqueta_adoptado"}),
                        etiquetas=labels,
                        etiqueta_adoptado=profile.etiqueta_adoptado,
                        origen_etiqueta="sintetica",
                    )
                )
                counts[profile.estado_publicado] += 1
            except ValidationError as exc:
                # El resumen puede reportar varios campos por fila, pero el perfil cuenta una vez.
                rejected_rows += 1
                for issue in exc.errors():
                    rejected[str(issue.get("loc", ["fila_invalida"])[0])] += 1
            except (AttributeError, ValueError, TypeError):
                rejected_rows += 1
                rejected["fila_invalida"] += 1

        total = len(rows)
        if total == 0 or not pets:
            raise CatalogSourceError("El CSV no contiene perfiles válidos; no se guardó una captura vacía.")
        return CatalogBatch(
            pets=pets,
            total_profiles=total,
            rejected_profiles=rejected_rows,
            available=counts["disponible"],
            unavailable=counts["no_disponible"],
            unpublished=counts["sin_publicar"],
            rejection_summary=dict(rejected),
        )

    @staticmethod
    def _convert_row(row: dict[str, str | None]) -> dict[str, object]:
        """Convierte valores CSV vacíos/tipados sin inferir ni inventar atributos."""
        if None in row:
            raise ValueError("la fila tiene más columnas que el encabezado")
        values: dict[str, object] = {key: (value or "").strip() for key, value in row.items()}
        for name in ("edad_estimada", "tamano_estimado", "condicion_especial", "etiqueta_adoptado"):
            raw = str(values[name]).casefold()
            if raw not in {"true", "false"}:
                raise ValueError(f"{name} debe ser true o false")
            values[name] = raw == "true"
        if values["edad_meses"] == "":
            values["edad_meses"] = None
        for name in ("condicion_detalle", "descripcion"):
            if values[name] == "":
                values[name] = None
        if values["orden_publicacion"] == "":
            raise ValueError("orden_publicacion requerido")
        values["orden_publicacion"] = int(str(values["orden_publicacion"]))
        if values["edad_meses"] is not None:
            values["edad_meses"] = int(str(values["edad_meses"]))
        return values
