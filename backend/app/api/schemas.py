"""Contratos públicos tipados de API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id_usuario: int
    nombre: str
    email: EmailStr
    rol: str


class CollectionRunResponse(BaseModel):
    id_ejecucion: int
    tipo_ejecucion: str
    fuente_datos: str
    referencia_fuente: str | None
    fecha_inicio: datetime
    fecha_fin: datetime | None
    semana: int
    perfiles_total: int
    perfiles_disponibles: int
    perfiles_no_disponibles: int
    perfiles_sin_publicar: int
    estado: str
    mensaje_error: str | None


class CollectionResultResponse(BaseModel):
    id_ejecucion: int
    fuente_datos: str
    referencia_fuente: str | None
    fecha_inicio: datetime
    fecha_fin: datetime
    semana: int
    perfiles_total: int
    perfiles_persistidos: int
    perfiles_rechazados: int
    perfiles_disponibles: int
    perfiles_no_disponibles: int
    perfiles_sin_publicar: int
    estado: str
    mensaje_error: str | None


class CollectionRunPage(BaseModel):
    items: list[CollectionRunResponse]
    limit: int
    offset: int


class CollectionOverview(BaseModel):
    ultima_captura: dict[str, object] | None
    proxima_ejecucion: datetime | None
    programacion_mensaje: str
