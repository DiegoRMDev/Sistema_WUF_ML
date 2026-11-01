"""Lecturas y persistencia versionada de la segmentación OE3."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


PROFILE_COLUMNS = """
    snapshot.id_snapshot, snapshot.id_ejecucion, snapshot.id_mascota,
    snapshot.sku, snapshot.nombre, snapshot.edad_meses, snapshot.edad_estimada,
    snapshot.tamano, snapshot.tamano_estimado, snapshot.nivel_energia,
    snapshot.condicion_especial
"""


class SegmentationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_available_profiles(self) -> dict[str, Any] | None:
        """Carga los snapshots disponibles de la captura completa más reciente."""
        run = self._session.execute(text("""
            SELECT id_ejecucion, semana, fecha_captura
            FROM ejecucion_recoleccion
            WHERE estado='completada'
            ORDER BY fecha_captura DESC, id_ejecucion DESC
            LIMIT 1
        """)).mappings().first()
        if run is None:
            return None
        rows = self._session.execute(text(f"""
            SELECT {PROFILE_COLUMNS}
            FROM snapshot_catalogo snapshot
            WHERE snapshot.id_ejecucion=:run_id
              AND snapshot.estado_detectado='disponible'
            ORDER BY snapshot.sku
        """), {"run_id": run["id_ejecucion"]}).mappings().all()
        return {"captura": dict(run), "items": [dict(row) for row in rows]}

    def available_profiles_for_run(self, run_id: int) -> list[dict[str, Any]]:
        """Recupera la captura original asociada a una versión para su gráfico histórico."""
        rows = self._session.execute(text(f"""
            SELECT {PROFILE_COLUMNS}
            FROM snapshot_catalogo snapshot
            WHERE snapshot.id_ejecucion=:run_id
              AND snapshot.estado_detectado='disponible'
            ORDER BY snapshot.sku
        """), {"run_id": run_id}).mappings().all()
        return [dict(row) for row in rows]

    def create_candidate(
        self,
        *,
        user_id: int,
        run_id: int,
        result: dict[str, Any],
        estimator: object,
        storage: Any,
        trained_at: datetime,
    ) -> dict[str, Any]:
        """Registra candidato y artefacto en una transacción con limpieza ante error."""
        filename: str | None = None
        try:
            model_id = int(self._session.execute(text("""
                SELECT nextval(pg_get_serial_sequence('modelo_segmentacion', 'id_modelo_segmentacion'))
            """)).scalar_one())
            version = f"v{model_id}"
            self._session.execute(text("""
                INSERT INTO modelo_segmentacion
                    (id_modelo_segmentacion, version, id_ejecucion_referencia, id_usuario, cantidad_clusters,
                     cantidad_perfiles, silhouette_score, inertia, variables,
                     resumen_clusters, parametros, artefacto_ruta, artefacto_sha256,
                     estado, es_vigente, fecha_entrenamiento)
                VALUES (
                    :model_id, :version, :run_id, :user_id, :cluster_count,
                    :profile_count, :silhouette, :inertia, CAST(:features AS jsonb),
                    CAST(:summaries AS jsonb), CAST(:parameters AS jsonb),
                    'pending.joblib', :placeholder_hash, 'candidato', FALSE, :trained_at
                )
            """), {
                "model_id": model_id,
                "version": version,
                "run_id": run_id,
                "user_id": user_id,
                "cluster_count": result["parameters"]["n_clusters"],
                "profile_count": len(result["profiles"]),
                "silhouette": result["silhouette_score"],
                "inertia": result["inertia"],
                "features": json.dumps(result["feature_names"]),
                "summaries": json.dumps(result["cluster_summaries"], ensure_ascii=False),
                "parameters": json.dumps(result["parameters"]),
                "placeholder_hash": "0" * 64,
                "trained_at": trained_at,
            })
            filename, digest = storage.save(model_id, estimator)
            self._session.execute(text("""
                UPDATE modelo_segmentacion
                SET version=:version, artefacto_ruta=:filename, artefacto_sha256=:digest
                WHERE id_modelo_segmentacion=:model_id
            """), {
                "version": version, "filename": filename, "digest": digest, "model_id": model_id,
            })
            self._session.commit()
            return self.get_model(model_id)  # type: ignore[return-value]
        except Exception:
            self._session.rollback()
            storage.delete(filename)
            raise

    def get_model(self, model_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            SELECT model.*, run.semana AS semana_referencia,
                   run.fecha_captura AS fecha_captura_referencia
            FROM modelo_segmentacion model
            JOIN ejecucion_recoleccion run
              ON run.id_ejecucion=model.id_ejecucion_referencia
            WHERE model.id_modelo_segmentacion=:model_id
        """), {"model_id": model_id}).mappings().first()
        return dict(row) if row else None

    def list_models(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            SELECT model.id_modelo_segmentacion, model.version, model.algoritmo,
                   model.cantidad_clusters, model.cantidad_perfiles, model.silhouette_score,
                   model.inertia, model.variables, model.resumen_clusters, model.parametros, model.estado,
                   model.es_vigente, model.fecha_entrenamiento,
                   run.semana AS semana_referencia, run.fecha_captura AS fecha_captura_referencia
            FROM modelo_segmentacion model
            JOIN ejecucion_recoleccion run
              ON run.id_ejecucion=model.id_ejecucion_referencia
            ORDER BY model.id_modelo_segmentacion DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def activate_with_assignments(
        self, model_id: int, assignments: list[dict[str, Any]], assigned_at: datetime,
    ) -> None:
        """Activa el candidato y guarda sus asignaciones para la captura actual."""
        try:
            model = self._session.execute(text("""
                SELECT estado FROM modelo_segmentacion WHERE id_modelo_segmentacion=:model_id FOR UPDATE
            """), {"model_id": model_id}).mappings().first()
            if model is None or model["estado"] != "candidato":
                raise ValueError("Solo se puede activar un candidato existente.")
            self._session.execute(text("""
                UPDATE modelo_segmentacion
                SET estado='anterior', es_vigente=FALSE WHERE es_vigente=TRUE
            """))
            self._session.execute(text("""
                UPDATE modelo_segmentacion
                SET estado='vigente', es_vigente=TRUE WHERE id_modelo_segmentacion=:model_id
            """), {"model_id": model_id})
            self._upsert_assignments(model_id, assignments, assigned_at)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def refresh_assignments(
        self, model_id: int, assignments: list[dict[str, Any]], assigned_at: datetime,
    ) -> None:
        """Actualiza solo los perfiles de la captura nueva, conservando la auditoría previa."""
        try:
            exists = self._session.execute(text("""
                SELECT 1 FROM modelo_segmentacion
                WHERE id_modelo_segmentacion=:model_id AND es_vigente=TRUE
            """), {"model_id": model_id}).first()
            if exists is None:
                raise ValueError("El modelo solicitado ya no es la segmentación vigente.")
            self._upsert_assignments(model_id, assignments, assigned_at)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _upsert_assignments(
        self, model_id: int, assignments: list[dict[str, Any]], assigned_at: datetime,
    ) -> None:
        for item in assignments:
            self._session.execute(text("""
                INSERT INTO asignacion_segmento
                    (id_modelo_segmentacion, id_snapshot, numero_segmento,
                     criterios_desfavorecidos, fecha_asignacion)
                VALUES (:model_id, :snapshot_id, :cluster, CAST(:criteria AS jsonb), :assigned_at)
                ON CONFLICT (id_modelo_segmentacion, id_snapshot) DO UPDATE
                SET numero_segmento=EXCLUDED.numero_segmento,
                    criterios_desfavorecidos=EXCLUDED.criterios_desfavorecidos,
                    fecha_asignacion=EXCLUDED.fecha_asignacion
            """), {
                "model_id": model_id,
                "snapshot_id": item["id_snapshot"],
                "cluster": item["numero_segmento"],
                "criteria": json.dumps(item["criterios_desfavorecidos"], ensure_ascii=False),
                "assigned_at": assigned_at,
            })

    def assignments_for_run(self, run_id: int, model_id: int) -> list[dict[str, Any]]:
        rows = self._session.execute(text(f"""
            SELECT assignment.id_asignacion_segmento, assignment.id_snapshot,
                   assignment.numero_segmento, assignment.criterios_desfavorecidos,
                   {PROFILE_COLUMNS}, model.version, model.resumen_clusters
            FROM asignacion_segmento assignment
            JOIN snapshot_catalogo snapshot ON snapshot.id_snapshot=assignment.id_snapshot
            JOIN modelo_segmentacion model
              ON model.id_modelo_segmentacion=assignment.id_modelo_segmentacion
            WHERE snapshot.id_ejecucion=:run_id
              AND assignment.id_modelo_segmentacion=:model_id
              AND snapshot.estado_detectado='disponible'
            ORDER BY assignment.numero_segmento, snapshot.sku
        """), {"run_id": run_id, "model_id": model_id}).mappings().all()
        return [dict(row) for row in rows]
