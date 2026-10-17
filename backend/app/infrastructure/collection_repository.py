"""Persistencia SQL de las ejecuciones y snapshots HU01."""

from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.catalog import CatalogPet


class CollectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        # Admite la base anterior y la v2 sin migrar datos ni perder la base ya existente.
        self._schema_v2 = self._has_v2_capture_schema()

    def _has_v2_capture_schema(self) -> bool:
        return bool(self._session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'ejecucion_recoleccion'
                  AND column_name = 'fecha_captura'
            )
        """)).scalar_one())

    def start_run(
        self,
        actor_id: int | None,
        started_at: datetime,
        capture_date: date,
        week: int,
        execution_type: str,
        source_name: str,
        source_reference: str | None,
    ) -> int:
        if self._schema_v2:
            statement = """
                INSERT INTO ejecucion_recoleccion
                    (id_usuario, tipo_ejecucion, fuente_datos, referencia_fuente,
                     fecha_captura, fecha_inicio, semana, estado)
                VALUES (:actor_id, :execution_type, :source_name, :source_reference,
                        :capture_date, :started_at, :week, 'en_proceso')
                RETURNING id_ejecucion
            """
        else:
            statement = """
                INSERT INTO ejecucion_recoleccion
                    (id_usuario, tipo_ejecucion, fuente_datos, referencia_fuente,
                     fecha_inicio, semana, estado)
                VALUES (:actor_id, :execution_type, :source_name, :source_reference,
                        :started_at, :week, 'en_proceso')
                RETURNING id_ejecucion
            """
        result = self._session.execute(text(statement), {
                "actor_id": actor_id,
                "execution_type": execution_type,
                "source_name": source_name,
                "source_reference": source_reference,
                "capture_date": capture_date,
                "started_at": started_at,
                "week": week,
            })
        self._session.commit()
        return int(result.scalar_one())

    def persist_capture(
        self, run_id: int, pets: list[CatalogPet], captured_at: datetime, week: int
    ) -> tuple[int, int]:
        persisted = 0
        rejected = 0
        try:
            self._validate_run_context(run_id, captured_at.date(), week)
            # Serializa upserts por SKU para mantener el orden de las capturas concurrentes.
            self._session.execute(text("SELECT pg_advisory_xact_lock(1479021123)"))
            for pet in pets:
                nested = self._session.begin_nested()
                try:
                    # El SKU reconcilia mascotas; cada CSV actualiza lo vigente y conserva su snapshot.
                    pet_id = self._upsert_pet(pet)
                    self._validate_pet_identity(pet_id, pet.sku)
                    snapshot_id = self._insert_snapshot(run_id, pet_id, pet, captured_at, week)
                    self._insert_snapshot_labels(snapshot_id, pet.etiquetas)
                    nested.commit()
                    persisted += 1
                except (IntegrityError, ValueError, TypeError):
                    nested.rollback()
                    rejected += 1
            self._validate_persisted_capture(run_id)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return persisted, rejected

    def _validate_run_context(self, run_id: int, capture_date: date, week: int) -> None:
        """Comprueba que el snapshot usa la fecha y semana del registro de ejecución."""
        if self._schema_v2:
            row = self._session.execute(text("""
                SELECT fecha_captura, semana, estado
                FROM ejecucion_recoleccion WHERE id_ejecucion = :run_id
            """), {"run_id": run_id}).mappings().first()
            if row is None or row["fecha_captura"] != capture_date or row["semana"] != week:
                raise ValueError("La fecha/semana del CSV no coincide con la ejecución de captura.")
            if row["estado"] != "en_proceso":
                raise ValueError("Solo se pueden guardar snapshots en una ejecución activa.")
        else:
            row = self._session.execute(text("""
                SELECT semana, estado
                FROM ejecucion_recoleccion WHERE id_ejecucion = :run_id
            """), {"run_id": run_id}).mappings().first()
            if row is None or row["semana"] != week or row["estado"] != "en_proceso":
                raise ValueError("La semana del snapshot no coincide con la ejecución activa.")

    def _validate_pet_identity(self, pet_id: int, sku: str) -> None:
        """Evita asociar el snapshot al registro de otra mascota."""
        stored_sku = self._session.execute(
            text("SELECT sku FROM mascota WHERE id_mascota = :pet_id"), {"pet_id": pet_id}
        ).scalar_one_or_none()
        if stored_sku != sku:
            raise ValueError("La mascota persistida no coincide con el SKU del snapshot.")

    def _validate_persisted_capture(self, run_id: int) -> None:
        """Valida en backend la relación mascota-snapshot-ejecución antes de confirmar."""
        date_check = (
            "OR snapshot.fecha_captura::date <> run.fecha_captura"
            if self._schema_v2 else
            "OR snapshot.semana <> EXTRACT(WEEK FROM snapshot.fecha_captura)::SMALLINT"
        )
        mismatch = self._session.execute(text(f"""
            SELECT EXISTS (
                SELECT 1
                FROM snapshot_catalogo AS snapshot
                JOIN ejecucion_recoleccion AS run
                  ON run.id_ejecucion = snapshot.id_ejecucion
                LEFT JOIN mascota AS pet
                  ON pet.id_mascota = snapshot.id_mascota
                WHERE snapshot.id_ejecucion = :run_id
                  AND (
                      pet.id_mascota IS NULL
                      OR snapshot.sku <> pet.sku
                      OR snapshot.semana <> run.semana
                      {date_check}
                  )
            )
        """), {"run_id": run_id}).scalar_one()
        if mismatch:
            raise ValueError("La relación entre mascota, snapshot y ejecución no es consistente.")

    def finish_run(
        self,
        run_id: int,
        finished_at: datetime,
        status: str,
        total: int,
        available: int,
        unavailable: int,
        unpublished: int,
        error_message: str | None,
    ) -> None:
        self._session.execute(
            text("""
                UPDATE ejecucion_recoleccion
                SET fecha_fin = :finished_at,
                    estado = :status,
                    perfiles_total = :total,
                    perfiles_disponibles = :available,
                    perfiles_no_disponibles = :unavailable,
                    perfiles_sin_publicar = :unpublished,
                    mensaje_error = :error_message
                WHERE id_ejecucion = :run_id
            """),
            {
                "run_id": run_id,
                "finished_at": finished_at,
                "status": status,
                "total": total,
                "available": available,
                "unavailable": unavailable,
                "unpublished": unpublished,
                "error_message": error_message,
            },
        )
        self._session.commit()

    def list_runs(self, limit: int, offset: int) -> list[dict[str, object]]:
        capture_date_sql = (
            "fecha_captura" if self._schema_v2 else
            "COALESCE((SELECT MIN(s.fecha_captura)::date FROM snapshot_catalogo s "
            "WHERE s.id_ejecucion = ejecucion_recoleccion.id_ejecucion), fecha_inicio::date)"
        )
        rows = self._session.execute(
            text(f"""
                SELECT id_ejecucion, tipo_ejecucion, fuente_datos, referencia_fuente,
                       {capture_date_sql} AS fecha_captura,
                       fecha_inicio, fecha_fin, semana,
                       perfiles_total, perfiles_disponibles, perfiles_no_disponibles,
                       perfiles_sin_publicar, estado, mensaje_error
                FROM ejecucion_recoleccion
                ORDER BY fecha_inicio DESC, id_ejecucion DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        ).mappings()
        return [dict(row) for row in rows]

    def latest_completed_run(self) -> dict[str, object] | None:
        capture_date_sql = (
            "fecha_captura" if self._schema_v2 else
            "COALESCE((SELECT MIN(s.fecha_captura)::date FROM snapshot_catalogo s "
            "WHERE s.id_ejecucion = ejecucion_recoleccion.id_ejecucion), fecha_inicio::date)"
        )
        row = self._session.execute(
            text(f"""
                SELECT id_ejecucion, fuente_datos, referencia_fuente,
                       {capture_date_sql} AS fecha_captura,
                       fecha_inicio, semana, perfiles_total,
                       perfiles_disponibles, perfiles_no_disponibles, perfiles_sin_publicar, estado
                FROM ejecucion_recoleccion
                WHERE estado = 'completada'
                ORDER BY fecha_fin DESC, id_ejecucion DESC
                LIMIT 1
            """)
        ).mappings().first()
        return dict(row) if row else None

    def _upsert_pet(self, pet: CatalogPet) -> int:
        values = self._pet_values(pet)
        existing_id = self._session.execute(
            text("SELECT id_mascota FROM mascota WHERE sku = :sku ORDER BY id_mascota LIMIT 1"),
            {"sku": pet.sku},
        ).scalar_one_or_none()
        if existing_id is None:
            row = self._session.execute(
                text("""
                    INSERT INTO mascota (
                        sku, nombre, especie, raza, sexo, edad_meses, edad_estimada,
                        tipo_pelaje, tamano, tamano_estimado, nivel_energia,
                        condicion_especial, condicion_detalle, descripcion,
                        orden_publicacion, estado_publicado, fecha_publicacion, url_perfil
                    ) VALUES (
                        :sku, :nombre, :especie, :raza, :sexo, :edad_meses, :edad_estimada,
                        :tipo_pelaje, :tamano, :tamano_estimado, :nivel_energia,
                        :condicion_especial, :condicion_detalle, :descripcion,
                        :orden_publicacion, :estado_publicado, :fecha_publicacion, :url_perfil
                    )
                    RETURNING id_mascota
                """),
                values,
            ).mappings().one()
            pet_id = int(row["id_mascota"])
        else:
            pet_id = int(existing_id)
            self._session.execute(
                text("""
                    UPDATE mascota SET
                        nombre=:nombre, especie=:especie, raza=:raza, sexo=:sexo,
                        edad_meses=:edad_meses, edad_estimada=:edad_estimada,
                        tipo_pelaje=:tipo_pelaje, tamano=:tamano,
                        tamano_estimado=:tamano_estimado, nivel_energia=:nivel_energia,
                        condicion_especial=:condicion_especial,
                        condicion_detalle=:condicion_detalle, descripcion=:descripcion,
                        orden_publicacion=:orden_publicacion,
                        estado_publicado=:estado_publicado, fecha_publicacion=:fecha_publicacion,
                        url_perfil=:url_perfil
                    WHERE id_mascota=:pet_id
                """),
                values | {"pet_id": pet_id},
            )
        if pet.etiquetas is not None:
            self._session.execute(
                text("DELETE FROM etiqueta_condicion WHERE id_mascota = :pet_id"), {"pet_id": pet_id}
            )
            for label in pet.etiquetas:
                self._session.execute(
                    text("INSERT INTO etiqueta_condicion (id_mascota, etiqueta) VALUES (:pet_id, :label)"),
                    {"pet_id": pet_id, "label": label},
                )
        return pet_id

    @staticmethod
    def _pet_values(pet: CatalogPet) -> dict[str, object]:
        return {
            "sku": pet.sku,
            "nombre": pet.nombre,
            "especie": pet.especie,
            "raza": pet.raza,
            "sexo": pet.sexo,
            "edad_meses": pet.edad_meses,
            "edad_estimada": pet.edad_estimada,
            "tipo_pelaje": pet.tipo_pelaje,
            "tamano": pet.tamano,
            "tamano_estimado": pet.tamano_estimado,
            "nivel_energia": pet.nivel_energia,
            "condicion_especial": pet.condicion_especial,
            "condicion_detalle": pet.condicion_detalle,
            "descripcion": pet.descripcion,
            "orden_publicacion": pet.orden_publicacion,
            "estado_publicado": pet.estado_publicado,
            "fecha_publicacion": pet.fecha_publicacion,
            "url_perfil": pet.url_perfil,
        }

    def _insert_snapshot(
        self, run_id: int, pet_id: int, pet: CatalogPet, captured_at: datetime, week: int
    ) -> int:
        values = self._pet_values(pet)
        values.update(
            {
                "pet_id": pet_id,
                "run_id": run_id,
                "week": week,
                "captured_at": captured_at,
                "estado_detectado": pet.estado_publicado,
                "etiqueta_adoptado": pet.etiqueta_adoptado,
                "origen_etiqueta": pet.origen_etiqueta,
            }
        )
        if self._schema_v2:
            statement = """
                INSERT INTO snapshot_catalogo (
                    id_mascota, id_ejecucion, semana, fecha_captura,
                    sku, nombre, especie, raza, sexo, edad_meses, edad_estimada,
                    tipo_pelaje, tamano, tamano_estimado, nivel_energia,
                    condicion_especial, condicion_detalle, descripcion, orden_publicacion,
                    estado_detectado, fecha_publicacion, url_perfil,
                    etiqueta_adoptado, origen_etiqueta
                ) VALUES (
                    :pet_id, :run_id, :week, :captured_at,
                    :sku, :nombre, :especie, :raza, :sexo, :edad_meses, :edad_estimada,
                    :tipo_pelaje, :tamano, :tamano_estimado, :nivel_energia,
                    :condicion_especial, :condicion_detalle, :descripcion, :orden_publicacion,
                    :estado_detectado, :fecha_publicacion, :url_perfil,
                    :etiqueta_adoptado, :origen_etiqueta
                ) RETURNING id_snapshot
            """
        else:
            statement = """
                INSERT INTO snapshot_catalogo (
                    id_mascota, id_dataset, id_ejecucion, semana, fecha_captura,
                    sku, nombre, especie, raza, sexo, edad_meses, edad_estimada,
                    tipo_pelaje, tamano, tamano_estimado, nivel_energia,
                    condicion_especial, condicion_detalle, descripcion, orden_publicacion,
                    estado_detectado, fecha_publicacion, url_perfil,
                    etiqueta_adoptado, origen_etiqueta
                ) VALUES (
                    :pet_id, NULL, :run_id, :week, :captured_at,
                    :sku, :nombre, :especie, :raza, :sexo, :edad_meses, :edad_estimada,
                    :tipo_pelaje, :tamano, :tamano_estimado, :nivel_energia,
                    :condicion_especial, :condicion_detalle, :descripcion, :orden_publicacion,
                    :estado_detectado, :fecha_publicacion, :url_perfil,
                    :etiqueta_adoptado, :origen_etiqueta
                ) RETURNING id_snapshot
            """
        row = self._session.execute(text(statement), values).mappings().one()
        return int(row["id_snapshot"])

    def _insert_snapshot_labels(self, snapshot_id: int, labels: tuple[str, ...] | None) -> None:
        for label in labels or ():
            self._session.execute(
                text("""
                    INSERT INTO snapshot_etiqueta_condicion (id_snapshot, etiqueta)
                    VALUES (:snapshot_id, :label)
                """),
                {"snapshot_id": snapshot_id, "label": label},
            )
