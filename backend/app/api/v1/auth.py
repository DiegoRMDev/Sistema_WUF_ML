"""Inicio de sesión y perfil del usuario autenticado."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.dependencies import CurrentUser, get_current_user
from app.api.schemas import LoginRequest, TokenResponse, UserResponse
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, verify_password
from app.infrastructure.database import get_db
from app.infrastructure.identity_repository import IdentityRepository

router = APIRouter(prefix="/auth", tags=["Autenticación"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_settings().login_rate_limit)
def login(
    request: Request,
    payload: LoginRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    row = IdentityRepository(session).get_login_credentials(str(payload.email))
    if row is None or not verify_password(payload.password, str(row["password_hash"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Correo o contraseña incorrectos."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(str(row["email"]), settings),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**asdict(user))
