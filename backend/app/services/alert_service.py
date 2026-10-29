"""Casos de uso HU07: consulta interna y registro auditable de atención."""

import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.infrastructure.alert_repository import AlertRepository


class AlertNotFoundError(ValueError):
    """La alerta solicitada no existe."""


class AlertTransitionError(ValueError):
    """El estado solicitado no corresponde al siguiente paso permitido."""


class AlertService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = AlertRepository(session)

    def list_alerts(self, state: str | None = None) -> dict[str, Any]:
        """Entrega las alertas y su historial sin exponer IDs de credenciales."""
        result = self._repository.list_alerts(state)
        return {
            "items": [_serialize_alert(item) for item in result["items"]],
            "total_abiertas": result["total_abiertas"],
        }

    def attend(
        self,
        alert_id: int,
        actor_id: int,
        next_state: str,
        note: str,
    ) -> dict[str, Any]:
        """Cambia el estado y guarda actor, fecha, transición y nota en una transacción."""
        try:
            alert = self._repository.get_alert_for_update(alert_id)
            if alert is None:
                raise AlertNotFoundError("No se encontró la alerta solicitada.")
            current_state = str(alert["estado"])
            allowed = {
                "pendiente": {"en_revision", "resuelta"},
                "en_revision": {"resuelta"},
            }
            if next_state not in allowed.get(current_state, set()):
                raise AlertTransitionError(
                    "La alerta ya fue resuelta o el cambio de estado no está permitido."
                )
            self._repository.add_attention(
                alert_id=alert_id,
                actor_id=actor_id,
                previous_state=current_state,
                next_state=next_state,
                note=note.strip(),
            )
            self._session.commit()
        except (AlertNotFoundError, AlertTransitionError):
            self._session.rollback()
            raise
        except Exception:
            self._session.rollback()
            raise

        updated = self._repository.get_alert(alert_id)
        if updated is None:
            raise AlertNotFoundError("La alerta dejó de estar disponible.")
        return _serialize_alert(updated)


def _serialize_alert(item: dict[str, Any]) -> dict[str, Any]:
    """Normaliza valores PostgreSQL a JSON y expresa horas en la zona de Lima."""
    row = dict(item)
    indicators = row.get("indicadores") or {}
    if isinstance(indicators, str):
        indicators = json.loads(indicators)
    row["indicadores"] = indicators
    observed_days = indicators.get("dias_sin_cambio_observado")
    row["dias_sin_cambio_observado"] = (
        int(observed_days) if observed_days is not None else None
    )
    for field in ("fecha_evaluacion", "fecha_captura"):
        value = row.get(field)
        if isinstance(value, (datetime, date)):
            row[field] = value.isoformat()
    for field in ("fecha", "fecha_ultima_deteccion"):
        row[field] = _lima_iso(row.get(field))
    row["historial_atencion"] = [
        {
            "estado_anterior": event["estado_anterior"],
            "estado_nuevo": event["estado_nuevo"],
            "fecha": _lima_iso(event["fecha"]),
            "nota": event["nota"],
            "atendido_por": event["atendido_por"],
        }
        for event in row.get("historial_atencion", [])
    ]
    return row


def _lima_iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    local = (
        value.replace(tzinfo=ZoneInfo("America/Lima"))
        if value.tzinfo is None else value.astimezone(ZoneInfo("America/Lima"))
    )
    return local.isoformat()
