"""Endpoints de consulta y exportación del reporte HU05."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_analyst_or_marketing
from app.infrastructure.database import get_db
from app.services.report_service import (
    ReportExportError,
    ReportNotFoundError,
    ReportService,
    ReportServiceError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reportes HU05"])


@router.get("/current")
def current_report(
    _user: CurrentUser = Depends(require_analyst_or_marketing),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    return ReportService(session).current()


@router.get("/history")
def report_history(
    _user: CurrentUser = Depends(require_analyst_or_marketing),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    return {"items": ReportService(session).history()}


@router.post("/export", status_code=status.HTTP_200_OK)
def export_report(
    formato: Literal["pdf", "xlsx"] = Query(),
    user: CurrentUser = Depends(require_analyst_or_marketing),
    session: Session = Depends(get_db),
) -> Response:
    try:
        content, filename, media_type = ReportService(session).export(user_id=user.id_usuario, formato=formato)
    except ReportServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "report_not_ready", "message": str(exc)},
        ) from exc
    except ReportExportError as exc:
        session.rollback()
        logger.error("HU05 falló al preparar el archivo; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "report_export_failed", "message": "No se pudo generar el reporte."},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.error("HU05 no pudo exportar; actor_id=%s; error_type=%s", user.id_usuario, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "report_export_failed", "message": "No se pudo generar el reporte."},
        ) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/history/{report_id}/export")
def export_saved_report(
    report_id: int,
    _user: CurrentUser = Depends(require_analyst_or_marketing),
    session: Session = Depends(get_db),
) -> Response:
    try:
        content, filename, media_type = ReportService(session).export_saved(report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "report_not_found", "message": str(exc)}) from exc
    except ReportExportError as exc:
        logger.error("HU05 falló al recuperar el reporte %s; error_type=%s", report_id, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "report_export_failed", "message": "No se pudo recuperar el archivo del reporte."},
        ) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
