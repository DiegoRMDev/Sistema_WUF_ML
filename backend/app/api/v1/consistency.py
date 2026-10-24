"""Endpoints HU04 para entrenar el árbol y consultar riesgos de consistencia."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_current_user, require_analyst
from app.api.schemas import ConsistencyTrainingRequest
from app.core.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.services.consistency_service import ConsistencyService, ConsistencyServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/consistency", tags=["Consistencia HU04"])


def _require_consistency_reader(user: CurrentUser) -> None:
    if user.rol not in {"analista", "ayuda"}:
        raise HTTPException(
            status_code=403,
            detail={"code": "insufficient_role", "message": "No tienes permiso para consultar estos riesgos."},
        )


@router.get("/latest")
def latest_consistency_report(
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Expone la evaluación vigente a Analista y Área de Ayuda autenticados."""
    _require_consistency_reader(user)
    return ConsistencyService(session, settings).latest_report()


@router.get("/history/{model_id}")
def consistency_version_report(
    model_id: int,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Permite revisar las métricas y evaluaciones guardadas de versiones anteriores."""
    _require_consistency_reader(user)
    if model_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_model_id", "message": "ID inválido."})
    try:
        return ConsistencyService(session, settings).version_report(model_id)
    except ConsistencyServiceError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "consistency_version_not_found", "message": str(exc)},
        ) from exc


@router.post("/train", status_code=201)
def train_consistency_model(
    request: ConsistencyTrainingRequest | None = None,
    user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Crea una versión reproducible del árbol y evalúa la captura completa más reciente."""
    try:
        return ConsistencyService(session, settings).train_and_evaluate(
            user.id_usuario,
            max_depth=request.profundidad_maxima if request else None,
            test_size=request.proporcion_prueba if request else None,
        )
    except ConsistencyServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "consistency_training_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU04 falló; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "consistency_training_failed", "message": "No se pudo evaluar la consistencia."},
        ) from exc
