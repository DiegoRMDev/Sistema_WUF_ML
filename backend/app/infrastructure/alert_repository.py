"""Persistencia PostgreSQL de alertas internas y sus cambios de atención."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def sync_high_priority_alerts(self, assessments: list[dict[str, Any]]) -> dict[str, int]:
        """Crea avisos nuevos o refresca la evidencia de los que siguen abiertos."""
        # Serializa la sincronización; el índice único sigue siendo la última defensa.
        self._session.execute(text("SELECT pg_advisory_xact_lock(1479021126)"))
        created = updated = 0
        for item in assessments:
            if item["nivel_riesgo"] != "alto":
                continue
            evaluation_id = int(item["id_evaluacion"])
            pet_id = int(item["id_mascota"])
            already_linked = self._session.execute(text("""
                SELECT 1
                FROM alerta_desactualizacion
                WHERE id_evaluacion_origen = :evaluation_id
                   OR id_evaluacion_ultima = :evaluation_id
                LIMIT 1
            """), {"evaluation_id": evaluation_id}).scalar_one_or_none()
            if already_linked:
                continue

            detected_at = datetime.now(ZoneInfo("America/Lima")).replace(tzinfo=None)
            indicators = item["indicadores"]
            no_change_days = indicators.get("dias_sin_cambio_observado")
            observed_duration = (
                f"{int(no_change_days)} días sin cambio observado"
                if no_change_days is not None
                else "días sin cambio observado no registrados"
            )
            message = (
                f"Prioridad alta de revisión; {observed_duration}. "
                f"{item['justificacion']}"
            )[:255]
            active = self._session.execute(text("""
                SELECT id_alerta
                FROM alerta_desactualizacion
                WHERE id_mascota = :pet_id
                  AND estado IN ('pendiente', 'en_revision')
                FOR UPDATE
            """), {"pet_id": pet_id}).scalar_one_or_none()
            if active is not None:
                self._session.execute(text("""
                    UPDATE alerta_desactualizacion
                    SET id_evaluacion_ultima = :evaluation_id,
                        fecha_ultima_deteccion = :detected_at,
                        nivel_riesgo = 'alto', mensaje = :message
                    WHERE id_alerta = :alert_id
                """), {
                    "evaluation_id": evaluation_id,
                    "detected_at": detected_at,
                    "message": message,
                    "alert_id": int(active),
                })
                updated += 1
                continue

            self._session.execute(text("""
                INSERT INTO alerta_desactualizacion (
                    id_mascota, id_evaluacion_origen, id_evaluacion_ultima,
                    fecha, fecha_ultima_deteccion, nivel_riesgo, mensaje, estado
                ) VALUES (
                    :pet_id, :evaluation_id, :evaluation_id,
                    :detected_at, :detected_at, 'alto', :message, 'pendiente'
                )
            """), {
                "pet_id": pet_id,
                "evaluation_id": evaluation_id,
                "detected_at": detected_at,
                "message": message,
            })
            created += 1
        return {"nuevas": created, "actualizadas": updated}

    def list_alerts(self, state: str | None = None) -> dict[str, Any]:
        rows = self._session.execute(text("""
            SELECT alert.id_alerta, alert.id_mascota, alert.id_evaluacion_origen,
                   alert.id_evaluacion_ultima, alert.fecha, alert.fecha_ultima_deteccion,
                   alert.nivel_riesgo, alert.mensaje, alert.estado,
                   latest_eval.justificacion, latest_eval.indicadores,
                   latest_eval.fecha_evaluacion, run.semana, run.fecha_captura,
                   snapshot.estado_detectado, pet.sku, snapshot.nombre,
                   model.version AS version_arbol
            FROM alerta_desactualizacion AS alert
            JOIN evaluacion_consistencia AS latest_eval
              ON latest_eval.id_evaluacion = alert.id_evaluacion_ultima
            JOIN modelo_consistencia AS model
              ON model.id_modelo_consistencia = latest_eval.id_modelo_consistencia
            JOIN ejecucion_recoleccion AS run
              ON run.id_ejecucion = latest_eval.id_ejecucion
            JOIN snapshot_catalogo AS snapshot
              ON snapshot.id_snapshot = latest_eval.id_snapshot
            JOIN mascota AS pet ON pet.id_mascota = alert.id_mascota
            -- El CAST permite a PostgreSQL tipar el filtro cuando llega como NULL ("Todos").
            WHERE (CAST(:state AS VARCHAR) IS NULL OR alert.estado = :state)
            ORDER BY CASE alert.estado WHEN 'pendiente' THEN 0
                      WHEN 'en_revision' THEN 1 ELSE 2 END,
                     alert.fecha DESC, pet.sku
        """), {"state": state}).mappings().all()
        items = [dict(row) for row in rows]
        alert_ids = [int(item["id_alerta"]) for item in items]
        histories: dict[int, list[dict[str, Any]]] = {alert_id: [] for alert_id in alert_ids}
        if alert_ids:
            events = self._session.execute(text("""
                SELECT attention.id_alerta, attention.id_usuario,
                       attention.estado_anterior, attention.estado_nuevo,
                       attention.fecha, attention.nota, user_account.nombre AS atendido_por
                FROM alerta_atencion AS attention
                JOIN usuario AS user_account ON user_account.id_usuario = attention.id_usuario
                WHERE attention.id_alerta = ANY(:alert_ids)
                ORDER BY attention.fecha, attention.id_atencion
            """), {"alert_ids": alert_ids}).mappings().all()
            for event in events:
                row = dict(event)
                histories[int(row["id_alerta"])].append(row)
        for item in items:
            item["historial_atencion"] = histories[int(item["id_alerta"])]

        opened = self._session.execute(text("""
            SELECT COUNT(*) FROM alerta_desactualizacion
            WHERE estado IN ('pendiente', 'en_revision')
        """)).scalar_one()
        return {"items": items, "total_abiertas": int(opened)}

    def get_alert_for_update(self, alert_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            SELECT id_alerta, id_mascota, estado
            FROM alerta_desactualizacion
            WHERE id_alerta = :alert_id
            FOR UPDATE
        """), {"alert_id": alert_id}).mappings().first()
        return dict(row) if row else None

    def add_attention(
        self,
        *,
        alert_id: int,
        actor_id: int,
        previous_state: str,
        next_state: str,
        note: str,
    ) -> None:
        self._session.execute(text("""
            INSERT INTO alerta_atencion (
                id_alerta, id_usuario, estado_anterior, estado_nuevo, fecha, nota
            ) VALUES (
                :alert_id, :actor_id, :previous_state, :next_state,
                (CURRENT_TIMESTAMP AT TIME ZONE 'America/Lima'), :note
            )
        """), {
            "alert_id": alert_id,
            "actor_id": actor_id,
            "previous_state": previous_state,
            "next_state": next_state,
            "note": note,
        })
        self._session.execute(text("""
            UPDATE alerta_desactualizacion
            SET estado = :next_state
            WHERE id_alerta = :alert_id
        """), {"next_state": next_state, "alert_id": alert_id})

    def get_alert(self, alert_id: int) -> dict[str, Any] | None:
        result = self.list_alerts()
        return next(
            (item for item in result["items"] if int(item["id_alerta"]) == alert_id),
            None,
        )
