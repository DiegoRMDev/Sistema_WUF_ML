"""API HU07 para consultar alertas internas y registrar su atención."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_current_user
from app.api.schemas import AlertAttentionRequest
from app.infrastructure.database import get_db
from app.services.alert_service import (
    AlertNotFoundError,
    AlertService,
    AlertTransitionError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["Alertas HU07"])


def _require_alert_reader(user: CurrentUser) -> None:
    if user.rol not in {"analista", "ayuda"}:
        raise HTTPException(
            status_code=403,
            detail={"code": "insufficient_role", "message": "No tienes permiso para consultar las alertas."},
        )


@router.get("")
def list_alerts(
    estado: Literal["pendiente", "en_revision", "resuelta"] | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """Analista y Área de Ayuda consultan la bandeja; solo Ayuda puede atender."""
    _require_alert_reader(user)
    return AlertService(session).list_alerts(estado)


@router.patch("/{alert_id}/attention")
def attend_alert(
    alert_id: int,
    request: AlertAttentionRequest,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """Registra un paso de atención; cada transición queda ligada al usuario autenticado."""
    if user.rol != "ayuda":
        raise HTTPException(
            status_code=403,
            detail={"code": "insufficient_role", "message": "Solo el Área de Ayuda puede atender alertas."},
        )
    if alert_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_alert_id", "message": "ID inválido."})
    try:
        return AlertService(session).attend(
            alert_id, user.id_usuario, request.estado_nuevo, request.nota
        )
    except AlertNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "alert_not_found", "message": str(exc)},
        ) from exc
    except AlertTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_alert_transition", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU07 falló al registrar atención; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "alert_attention_failed", "message": "No se pudo guardar la atención de la alerta."},
        ) from exc
