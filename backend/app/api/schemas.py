"""Contratos públicos tipados de API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


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
    fecha_captura: date
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
    fecha_captura: date
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


class DatasetCreateRequest(BaseModel):
    """Periodo de capturas completas que define también el horizonte de seguimiento."""

    model_config = ConfigDict(extra="forbid")

    fecha_desde: date
    fecha_hasta: date

    @model_validator(mode="after")
    def validate_period(self) -> "DatasetCreateRequest":
        if self.fecha_hasta <= self.fecha_desde:
            raise ValueError("La fecha final debe ser posterior a la inicial.")
        return self


class ModelTrainingRequest(BaseModel):
    """Parámetros acotados que el Analista puede elegir para HU03."""

    model_config = ConfigDict(extra="forbid")

    id_dataset: int = Field(gt=0)
    proporcion_prueba: float = Field(ge=0.1, le=0.4)
    cantidad_arboles: int = Field(ge=50, le=1000)
    profundidad_maxima: int | None = Field(default=None, ge=2, le=50)


class ConsistencyTrainingRequest(BaseModel):
    """Opciones acotadas que el Analista puede ajustar para entrenar HU04."""

    model_config = ConfigDict(extra="forbid")

    profundidad_maxima: int = Field(default=3, ge=1, le=4)
    proporcion_prueba: float = Field(default=0.25, ge=0.1, le=0.4)

    @field_validator("proporcion_prueba")
    @classmethod
    def validate_test_size_choice(cls, value: float) -> float:
        if value not in {0.2, 0.25, 0.3}:
            raise ValueError("El porcentaje de prueba debe ser 20 %, 25 % o 30 %.")
        return value
