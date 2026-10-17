"""Creación del engine y sesiones PostgreSQL."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(
    settings.database_url.get_secret_value(),
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def verify_hu01_schema() -> None:
    """Falla al iniciar si faltan columnas requeridas por las capturas HU01."""
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT table_name, column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND (
                  (table_name = 'snapshot_catalogo' AND column_name IN ('etiqueta_adoptado', 'origen_etiqueta'))
                  OR (table_name = 'ejecucion_recoleccion'
                      AND column_name IN ('fuente_datos', 'referencia_fuente'))
                  OR (table_name = 'dataset_historico' AND column_name = 'origen_etiquetas')
              )
        """)).mappings().all()
    columns = {(row["table_name"], row["column_name"]): row["is_nullable"] for row in rows}
    if (
        columns.get(("snapshot_catalogo", "etiqueta_adoptado")) != "YES"
        or columns.get(("snapshot_catalogo", "origen_etiqueta")) != "YES"
        or columns.get(("ejecucion_recoleccion", "fuente_datos")) != "NO"
        or columns.get(("ejecucion_recoleccion", "referencia_fuente")) != "YES"
        or columns.get(("dataset_historico", "origen_etiquetas")) != "NO"
    ):
        raise RuntimeError(
            "La base no tiene lista HU01 CSV: aplique las migraciones HU01 anteriores y "
            "backend/upgrade_hu01_csv.sql."
        )
