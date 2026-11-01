"""Operaciones HU06: entrenamiento y aplicación de K-Means para OE3."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_analyst
from app.api.schemas import SegmentationTrainingRequest
from app.core.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.services.segmentation_service import SegmentationService, SegmentationServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/segmentation", tags=["Segmentación OE3"])


@router.get("/options")
def segmentation_options(
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return SegmentationService(session, settings).options()


@router.get("/models")
def segmentation_models(
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, list[dict[str, object]]]:
    return {"items": SegmentationService(session, settings).list_models()}


@router.get("/models/{model_id}/scatter")
def segmentation_scatter(
    model_id: int,
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Devuelve las coordenadas 2D de una versión para visualización, sin alterar el modelo."""
    if model_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_model_id", "message": "ID inválido."})
    try:
        return SegmentationService(session, settings).scatter_plot(model_id)
    except SegmentationServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "segmentation_plot_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("No se pudo preparar el gráfico OE3; error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "segmentation_plot_failed", "message": "No se pudo cargar el gráfico de segmentación."},
        ) from exc


@router.post("/models/train", status_code=status.HTTP_201_CREATED)
def train_segmentation(
    request: SegmentationTrainingRequest,
    user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return SegmentationService(session, settings).train(
            user_id=user.id_usuario,
            cluster_count=request.cantidad_clusters,
        )
    except SegmentationServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "segmentation_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("OE3 K-Means falló; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "segmentation_failed", "message": "No se pudo entrenar K-Means."},
        ) from exc


@router.post("/models/{model_id}/activate")
def activate_segmentation(
    model_id: int,
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if model_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_model_id", "message": "ID inválido."})
    try:
        return SegmentationService(session, settings).activate(model_id)
    except SegmentationServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "segmentation_activation_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("OE3 no pudo activar la segmentación; error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "segmentation_activation_failed", "message": "No se pudo activar el modelo."},
        ) from exc


@router.post("/models/current/refresh")
def refresh_segmentation(
    _user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return SegmentationService(session, settings).refresh()
    except SegmentationServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "segmentation_refresh_not_ready", "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("OE3 no pudo actualizar la captura; error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "segmentation_refresh_failed", "message": "No se pudieron actualizar los segmentos."},
        ) from exc
