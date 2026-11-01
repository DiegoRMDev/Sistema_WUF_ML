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
    """Comprueba que las estructuras de recolección y dataset estén completas."""
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
            "El esquema PostgreSQL no incluye las estructuras requeridas por HU01/HU02. "
            "Para la instalación actual, crea una base vacía y ejecuta "
            "backend/schema_wuf_predict_db.sql."
        )


def verify_hu03_schema() -> None:
    """Comprueba que el esquema de instalación limpia conserva la persistencia HU03."""
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
    # Los esquemas históricos previos a capturas versionadas no habilitan HU03.
    if ("ejecucion_recoleccion", "fecha_captura") not in available:
        return
    if not required.issubset(available):
        raise RuntimeError(
            "La base conectada no incluye el esquema limpio requerido para los módulos actuales. "
            "Crea una base vacía y ejecuta backend/schema_wuf_predict_db.sql."
        )


def verify_hu04_schema() -> None:
    """Comprueba que la instalación limpia conserve las estructuras de HU04."""
    with engine.connect() as connection:
        tables = set(connection.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
        """)).scalars().all())
    # Los esquemas históricos sin capturas versionadas no habilitan la verificación de HU04.
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
            "La base conectada no incluye la persistencia de HU04. Crea una base vacía y ejecuta "
            "backend/schema_wuf_predict_db.sql."
        )


def verify_hu07_schema() -> None:
    """Comprueba que la base configurada use la instalación limpia con auditoría HU07."""
    required = {
        ("alerta_desactualizacion", "id_evaluacion_origen"),
        ("alerta_desactualizacion", "id_evaluacion_ultima"),
        ("alerta_desactualizacion", "fecha_ultima_deteccion"),
        ("alerta_atencion", "id_alerta"),
        ("alerta_atencion", "id_usuario"),
        ("alerta_atencion", "estado_anterior"),
        ("alerta_atencion", "estado_nuevo"),
        ("alerta_atencion", "nota"),
    }
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
        """)).all()
    available = {(row[0], row[1]) for row in rows}
    if not required.issubset(available):
        raise RuntimeError(
            "La base conectada no incluye HU07. Crea una base nueva y vacía y ejecuta "
            "backend/schema_wuf_predict_db.sql; no apliques ese instalador sobre una base existente."
        )


def verify_hu06_schema() -> None:
    """Exige las tablas limpias que guardan los modelos y asignaciones K-Means de OE3."""
    required_tables = {"modelo_segmentacion", "asignacion_segmento", "reporte_segmento_detalle"}
    required_columns = {
        ("reporte_priorizacion", "id_ejecucion"),
        ("reporte_priorizacion", "id_modelo_segmentacion"),
        ("modelo_segmentacion", "silhouette_score"),
        ("modelo_segmentacion", "artefacto_sha256"),
        ("asignacion_segmento", "id_snapshot"),
        ("asignacion_segmento", "numero_segmento"),
    }
    with engine.connect() as connection:
        tables = set(connection.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema=current_schema()
        """)).scalars().all())
        columns = {
            (row[0], row[1]) for row in connection.execute(text("""
                SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema=current_schema()
            """)).all()
        }
    if not required_tables.issubset(tables) or not required_columns.issubset(columns):
        raise RuntimeError(
            "Falta el esquema limpio de segmentación OE3. Crea una base vacía y ejecuta "
            "backend/schema_wuf_predict_db.sql; no lo ejecutes como migración sobre una base con datos."
        )
