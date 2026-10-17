"""Dependencias de autenticación y autorización."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.infrastructure.collection_repository import CollectionRepository
from app.infrastructure.database import get_db
from app.infrastructure.identity_repository import IdentityRepository
from app.services.collection_query_service import CollectionQueryService

bearer_scheme = HTTPBearer(auto_error=False)
_ROLE_ALIASES = {
    "analista": "analista",
    "analista de datos": "analista",
    "marketing": "marketing",
    "área de ayuda": "ayuda",
    "area de ayuda": "ayuda",
    "ayuda": "ayuda",
}


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id_usuario: int
    nombre: str
    email: str
    rol: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_authentication", "message": "Autenticación requerida."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise invalid
    email = decode_access_token(credentials.credentials, settings)
    if email is None:
        raise invalid
    row = IdentityRepository(session).get_user_by_email(email)
    role = _ROLE_ALIASES.get(str(row["rol"]).casefold()) if row else None
    if row is None or role is None:
        raise invalid
    return CurrentUser(int(row["id_usuario"]), str(row["nombre"]), str(row["email"]), role)


def require_analyst(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.rol != "analista":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "insufficient_role", "message": "Esta operación requiere el rol Analista."},
        )
    return user


def get_collection_query_service(
    session: Session = Depends(get_db),
) -> CollectionQueryService:
    return CollectionQueryService(CollectionRepository(session))
