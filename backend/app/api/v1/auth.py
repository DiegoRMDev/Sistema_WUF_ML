"""Inicio de sesión y perfil del usuario autenticado."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.dependencies import CurrentUser, get_current_user
from app.api.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    TokenResponse,
    UserResponse,
)
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, verify_password
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


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: ProfileUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserResponse:
    """Guarda el nombre del usuario autenticado y devuelve el perfil actualizado."""
    repository = IdentityRepository(session)
    try:
        row = repository.update_name(user.id_usuario, payload.nombre)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "code": "user_not_found", "message": "No se encontró el usuario autenticado."
            })
        session.commit()
        return UserResponse(
            id_usuario=int(row["id_usuario"]),
            nombre=str(row["nombre"]),
            email=str(row["email"]),
            rol=user.rol,
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "profile_update_failed", "message": "No se pudo actualizar el perfil."},
        ) from exc


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    """Comprueba la contraseña actual y guarda el hash de la nueva contraseña."""
    repository = IdentityRepository(session)
    credentials = repository.get_login_credentials(user.email)
    if credentials is None or not verify_password(
        payload.current_password, str(credentials["password_hash"])
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "current_password_invalid", "message": "La contraseña actual no es correcta."},
        )
    try:
        repository.update_password_hash(user.id_usuario, hash_password(payload.new_password))
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "password_change_failed", "message": "No se pudo cambiar la contraseña."},
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
