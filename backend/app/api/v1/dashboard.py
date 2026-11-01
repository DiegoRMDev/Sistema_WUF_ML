"""Consultas resumidas HU08 para los roles que pueden acceder al Dashboard."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard HU08"])


@router.get("/summary")
def dashboard_summary(
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Entrega conteos y evolución sin exponer datos personales ni modificar registros."""
    try:
        return DashboardService(session, settings).summary()
    except Exception as exc:
        session.rollback()
        logger.error("HU08 no pudo cargar el Dashboard; error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"code": "dashboard_load_failed", "message": "No se pudo cargar el Dashboard."},
        ) from exc
