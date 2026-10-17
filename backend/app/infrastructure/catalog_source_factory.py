"""Construye el adaptador CSV de HU01 con referencias ya procesadas."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.catalog import CatalogSource
from app.infrastructure.csv_catalog_source import CsvCatalogSource


def create_catalog_source(
    settings: Settings, session: Session, filename: str, content: bytes
) -> CatalogSource:
    """Construye la fuente desde el archivo subido por el Analista."""
    used_references = set(
        session.execute(
            text("""
                SELECT referencia_fuente
                FROM ejecucion_recoleccion
                WHERE fuente_datos = 'csv_simulada' AND referencia_fuente IS NOT NULL
                  AND estado IN ('en_proceso', 'completada', 'parcial')
            """)
        ).scalars()
    )
    return CsvCatalogSource(settings, filename, content, used_references)
