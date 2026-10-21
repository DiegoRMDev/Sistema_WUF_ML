"""API HU03 para entrenar, consultar y publicar versiones de Random Forest."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_current_user, require_analyst
from app.api.schemas import ModelTrainingRequest
from app.core.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.services.model_service import ModelService, ModelServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["Entrenamiento HU03"])


@router.get("/predictions")
def catalog_predictions(
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return ModelService(session, settings).catalog_predictions()


@router.get("/options")
def model_options(
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return ModelService(session, settings).options()


@router.get("")
def list_models(
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, list[dict[str, object]]]:
    return {"items": ModelService(session, settings).list_models()}


@router.post("/train", status_code=status.HTTP_201_CREATED)
def train_model(
    request: ModelTrainingRequest,
    user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return ModelService(session, settings).train(
            dataset_id=request.id_dataset,
            test_size=request.proporcion_prueba,
            n_estimators=request.cantidad_arboles,
            max_depth=request.profundidad_maxima,
        )
    except ModelServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "model_training_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU03 falló; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "model_training_failed", "message": "No se pudo completar el entrenamiento."},
        ) from exc


@router.post("/{model_id}/activate")
def activate_model(
    model_id: int,
    user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if model_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_model_id", "message": "ID inválido."})
    try:
        return ModelService(session, settings).activate(model_id)
    except ModelServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "model_activation_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU03 no pudo activar modelo; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "model_activation_failed", "message": "No se pudo publicar el modelo."},
        ) from exc


@router.post("/{model_id}/refresh-predictions")
def refresh_predictions(
    model_id: int,
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if model_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_model_id", "message": "ID inválido."})
    try:
        return ModelService(session, settings).refresh_predictions(model_id)
    except ModelServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "model_refresh_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU03 no pudo actualizar predicciones; error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "model_refresh_failed", "message": "No se pudieron actualizar las predicciones."},
        ) from exc
