"""Tipos y puertos del dominio de catálogo."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CatalogPet:
    sku: str
    nombre: str
    especie: str
    raza: str
    sexo: str
    edad_meses: int | None
    edad_estimada: bool
    tipo_pelaje: str
    tamano: str
    tamano_estimado: bool
    nivel_energia: str
    condicion_especial: bool
    condicion_detalle: str | None
    descripcion: str | None
    orden_publicacion: int
    estado_publicado: str
    fecha_publicacion: date
    url_perfil: str
    etiquetas: tuple[str, ...] | None = None
    id_mascota: int | None = None
    # Etiqueta de ejemplo explícita; su procedencia evita confundirla con adopción verificada.
    etiqueta_adoptado: bool | None = None
    origen_etiqueta: str | None = None


class CatalogSource(Protocol):
    """Puerto para una fuente de catálogo intercambiable."""

    source_name: str
    source_reference: str | None
    capture_date: date

    def fetch_pets(self) -> "CatalogBatch": ...


@dataclass(frozen=True, slots=True)
class CatalogBatch:
    pets: list[CatalogPet]
    total_profiles: int
    rejected_profiles: int
    available: int
    unavailable: int
    unpublished: int
    rejection_summary: dict[str, int]


class CatalogSourceError(Exception):
    """Error seguro al localizar, leer o validar la fuente configurada."""


class CatalogAlreadyImported(CatalogSourceError):
    """Indica que el mismo nombre de archivo ya produjo una captura válida."""
