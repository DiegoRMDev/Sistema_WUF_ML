"""API HU02: generación, consulta y exportación del Dataset Histórico."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_analyst
from app.api.schemas import DatasetCreateRequest
from app.infrastructure.database import get_db
from app.infrastructure.dataset_repository import DatasetInputError
from app.services.dataset_service import DatasetService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["Dataset histórico"])


@router.get("")
def list_datasets(
    _user: CurrentUser = Depends(require_analyst), session: Session = Depends(get_db)
) -> dict[str, list[dict[str, object]]]:
    return {"items": DatasetService.from_session(session).list_datasets()}


@router.get("/sources")
def list_dataset_sources(
    _user: CurrentUser = Depends(require_analyst), session: Session = Depends(get_db)
) -> dict[str, list[dict[str, object]]]:
    return {"items": DatasetService.from_session(session).list_completed_runs()}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_dataset(
    request: DatasetCreateRequest,
    user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        dataset_id = DatasetService.from_session(session).create_dataset(
            request.fecha_desde, request.fecha_hasta
        )
    except DatasetInputError as exc:
        raise HTTPException(status_code=422, detail={"code": "dataset_not_ready", "message": str(exc)}) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU02 no pudo generar dataset; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(status_code=500, detail={
            "code": "dataset_generation_failed", "message": "No se pudo generar el dataset histórico."
        }) from exc
    result = DatasetService.from_session(session).get_dataset(dataset_id)
    return result["dataset"] if result else {"id_dataset": dataset_id}


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int, _user: CurrentUser = Depends(require_analyst), session: Session = Depends(get_db)
) -> dict[str, object]:
    if dataset_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_dataset_id", "message": "ID inválido."})
    result = DatasetService.from_session(session).get_dataset(dataset_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "dataset_not_found", "message": "Dataset no encontrado."})
    return result


@router.get("/{dataset_id}/export")
def export_dataset(
    dataset_id: int, _user: CurrentUser = Depends(require_analyst), session: Session = Depends(get_db)
) -> Response:
    if dataset_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_dataset_id", "message": "ID inválido."})
    content = DatasetService.from_session(session).export_csv(dataset_id)
    if content is None:
        raise HTTPException(status_code=404, detail={"code": "dataset_not_found", "message": "Dataset no encontrado."})
    return Response(content=content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="dataset_{dataset_id}.csv"'})
