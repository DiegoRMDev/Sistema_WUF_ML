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


def verify_hu03_schema() -> None:
    """Falla temprano si el esquema v2/v3 todavía no incluye persistencia HU03."""
    required = {
        ("modelo_predictivo", "estado"),
        ("modelo_predictivo", "metadatos_entrenamiento"),
        ("modelo_predictivo", "artefacto_ruta"),
        ("modelo_predictivo", "artefacto_sha256"),
        ("modelo_predictivo", "es_vigente"),
        ("prediccion", "id_ejecucion"),
    }
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
        """)).all()
    available = {(row[0], row[1]) for row in rows}
    # La base original sigue disponible para HU01; HU03 requiere el esquema v2/v3.
    if ("ejecucion_recoleccion", "fecha_captura") not in available:
        return
    if not required.issubset(available):
        raise RuntimeError(
            "Falta aplicar backend/upgrade_hu03_ml.sql en la base v2/v3 antes de iniciar HU03."
        )


def verify_hu04_schema() -> None:
    """Informa al iniciar si falta la persistencia requerida por HU04 en el esquema v4."""
    with engine.connect() as connection:
        tables = set(connection.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
        """)).scalars().all())
    # Las instalaciones antiguas se conservan para HU01; HU04 está disponible en el esquema v4.
    if "ejecucion_recoleccion" not in tables:
        return
    with engine.connect() as connection:
        capture_columns = set(connection.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'ejecucion_recoleccion'
        """)).scalars().all())
        hu04_columns = {
            (row[0], row[1]) for row in connection.execute(text("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name IN ('modelo_consistencia', 'evaluacion_consistencia')
            """)).all()
        }
    if "fecha_captura" not in capture_columns:
        return
    required = {
        ("modelo_consistencia", "artefacto_sha256"),
        ("modelo_consistencia", "metadatos_entrenamiento"),
        ("evaluacion_consistencia", "id_snapshot"),
        ("evaluacion_consistencia", "justificacion"),
    }
    if not {"modelo_consistencia", "evaluacion_consistencia"}.issubset(tables) or not required.issubset(hu04_columns):
        raise RuntimeError(
            "Falta ejecutar backend/upgrade_hu04_consistency.sql para habilitar HU04."
        )
