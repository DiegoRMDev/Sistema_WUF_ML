"""Endpoints HU01: captura manual e historial de ejecuciones."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    CurrentUser,
    get_collection_query_service,
    require_analyst,
)
from app.api.schemas import CollectionOverview, CollectionResultResponse, CollectionRunPage
from app.core.config import Settings, get_settings
from app.domain.catalog import CatalogAlreadyImported, CatalogSourceError
from app.infrastructure.catalog_source_factory import create_catalog_source
from app.infrastructure.collection_repository import CollectionRepository
from app.infrastructure.database import get_db
from app.services.collection_query_service import CollectionQueryService
from app.services.collection_service import CollectionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collection-runs", tags=["Recolección"])


@router.post("", response_model=CollectionResultResponse, status_code=status.HTTP_201_CREATED)
async def create_collection_run(
    file: UploadFile = File(..., description="Archivo CSV de la captura que se desea importar"),
    user: CurrentUser = Depends(require_analyst),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CollectionResultResponse:
    try:
        # Leer como máximo un byte sobre el límite para rechazar archivos grandes sin cargarlos completos.
        content = await file.read(settings.catalog_csv_max_bytes + 1)
        await file.close()
        if len(content) > settings.catalog_csv_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "csv_too_large", "message": "El CSV excede el tamaño máximo permitido."},
            )
        source = create_catalog_source(settings, session, file.filename or "", content)
        service = CollectionService(source=source, repository=CollectionRepository(session))
        result = service.execute(actor_id=user.id_usuario)
    except CatalogAlreadyImported as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "csv_already_imported", "message": str(exc)},
        ) from exc
    except CatalogSourceError as exc:
        logger.warning("HU01 rechazó el CSV; actor_id=%s", user.id_usuario)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_csv", "message": str(exc)},
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "HU01 falló durante persistencia; actor_id=%s; error_type=%s",
            user.id_usuario,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "collection_failed", "message": "La recolección no pudo completarse."},
        ) from exc
    return CollectionResultResponse(**result)


@router.get("", response_model=CollectionRunPage)
def list_collection_runs(
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    _user: CurrentUser = Depends(require_analyst),
    service: CollectionQueryService = Depends(get_collection_query_service),
) -> CollectionRunPage:
    settings = get_settings()
    page_limit = limit or settings.api_page_size_default
    page_offset = offset or 0
    if page_limit > settings.api_page_size_max or page_offset > settings.api_offset_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "pagination_limit_exceeded", "message": "El límite de paginación configurado fue excedido."},
        )
    runs = service.list_runs(page_limit, page_offset)
    return CollectionRunPage(items=runs, limit=page_limit, offset=page_offset)


@router.get("/overview", response_model=CollectionOverview)
def get_collection_overview(
    _user: CurrentUser = Depends(require_analyst),
    service: CollectionQueryService = Depends(get_collection_query_service),
) -> CollectionOverview:
    latest = service.get_overview()
    return CollectionOverview(
        ultima_captura=latest,
        proxima_ejecucion=None,
        programacion_mensaje="Selecciona un archivo CSV para iniciar una recolección manual.",
    )
