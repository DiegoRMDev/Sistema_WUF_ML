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
    """Acepta el esquema HU01 anterior o v2 y rechaza esquemas incompletos."""
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT table_name, column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
        """)).mappings().all()
    columns = {(row["table_name"], row["column_name"]): row["is_nullable"] for row in rows}
    common_schema_is_valid = not (
        columns.get(("snapshot_catalogo", "etiqueta_adoptado")) != "YES"
        or columns.get(("snapshot_catalogo", "origen_etiqueta")) != "YES"
        or columns.get(("ejecucion_recoleccion", "fuente_datos")) != "NO"
        or columns.get(("ejecucion_recoleccion", "referencia_fuente")) != "YES"
        or columns.get(("dataset_historico", "origen_etiquetas")) != "NO"
    )
    v2_schema = ("ejecucion_recoleccion", "fecha_captura") in columns
    if v2_schema:
        v2_schema_is_valid = not (
            columns.get(("ejecucion_recoleccion", "fecha_captura")) != "NO"
            or columns.get(("snapshot_catalogo", "id_ejecucion")) != "NO"
            or columns.get(("dataset_snapshot", "id_snapshot")) != "NO"
            or columns.get(("dataset_ejecucion", "id_ejecucion")) != "NO"
            or columns.get(("dataset_detalle", "etiqueta_catalogo")) != "NO"
            or columns.get(("dataset_detalle", "id_snapshot_referencia")) != "NO"
        )
    else:
        v2_schema_is_valid = ("snapshot_catalogo", "id_dataset") in columns
    if not common_schema_is_valid or not v2_schema_is_valid:
        raise RuntimeError(
            "El esquema PostgreSQL no corresponde a HU01/HU02 v2. "
            "Verifica que ejecutaste el SQL correspondiente a la base configurada."
        )
