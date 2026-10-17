"""Configuración tipada cargada desde el entorno."""

from functools import lru_cache
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WUF Predict API"
    environment: str = "development"
    database_url: SecretStr
    jwt_secret: SecretStr
    jwt_issuer: str = "wuf-predict"
    access_token_minutes: int = 30
    login_attempts_per_minute: int = 5
    api_page_size_default: int = 20
    api_page_size_max: int = 100
    api_offset_max: int = 100_000
    catalog_csv_max_bytes: int = 20_000_000
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_page_size_bounds(self) -> "Settings":
        if self.api_page_size_default > self.api_page_size_max:
            raise ValueError("API_PAGE_SIZE_DEFAULT no puede exceder API_PAGE_SIZE_MAX.")
        return self

    @field_validator("access_token_minutes")
    @classmethod
    def validate_token_lifetime(cls, value: int) -> int:
        if not 1 <= value <= 1440:
            raise ValueError("ACCESS_TOKEN_MINUTES debe estar entre 1 y 1440.")
        return value

    @field_validator("login_attempts_per_minute")
    @classmethod
    def validate_login_rate(cls, value: int) -> int:
        if not 1 <= value <= 60:
            raise ValueError("LOGIN_ATTEMPTS_PER_MINUTE debe estar entre 1 y 60.")
        return value

    @field_validator("api_page_size_default", "api_page_size_max")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if not 1 <= value <= 1000:
            raise ValueError("El tamaño de página de API debe estar entre 1 y 1000.")
        return value

    @field_validator("api_offset_max")
    @classmethod
    def validate_api_offset(cls, value: int) -> int:
        if not 0 <= value <= 1_000_000:
            raise ValueError("API_OFFSET_MAX está fuera del rango permitido.")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or "REEMPLAZAR" in secret.upper():
            raise ValueError("JWT_SECRET debe ser aleatorio, reemplazado y tener al menos 32 caracteres.")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins or "*" in origins:
            raise ValueError("CORS_ORIGINS debe enumerar orígenes explícitos y no puede contener '*'.")
        return value

    @field_validator("catalog_csv_max_bytes")
    @classmethod
    def validate_csv_limit(cls, value: int) -> int:
        if not 1024 <= value <= 100_000_000:
            raise ValueError("CATALOG_CSV_MAX_BYTES debe estar entre 1024 y 100000000.")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def login_rate_limit(self) -> str:
        return f"{self.login_attempts_per_minute}/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
