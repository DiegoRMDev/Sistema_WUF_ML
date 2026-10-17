"""Consultas SQL del módulo de identidad."""

from sqlalchemy import text
from sqlalchemy.orm import Session


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_login_credentials(self, email: str) -> dict[str, str] | None:
        row = self._session.execute(
            text("SELECT email, password_hash FROM usuario WHERE lower(email) = lower(:email)"),
            {"email": email},
        ).mappings().first()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict[str, object] | None:
        row = self._session.execute(
            text("SELECT id_usuario, nombre, email, rol FROM usuario WHERE lower(email) = lower(:email)"),
            {"email": email},
        ).mappings().first()
        return dict(row) if row else None
