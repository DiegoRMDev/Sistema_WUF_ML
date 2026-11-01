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

    def update_name(self, user_id: int, name: str) -> dict[str, object] | None:
        """Actualiza el nombre visible sin cambiar la identidad de inicio de sesión."""
        row = self._session.execute(
            text("""
                UPDATE usuario
                SET nombre = :name
                WHERE id_usuario = :user_id
                RETURNING id_usuario, nombre, email, rol
            """),
            {"user_id": user_id, "name": name},
        ).mappings().first()
        return dict(row) if row else None

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        """Guarda el hash Argon2 de la nueva contraseña, nunca la contraseña original."""
        self._session.execute(
            text("UPDATE usuario SET password_hash = :password_hash WHERE id_usuario = :user_id"),
            {"user_id": user_id, "password_hash": password_hash},
        )
