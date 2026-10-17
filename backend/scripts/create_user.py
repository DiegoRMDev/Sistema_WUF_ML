"""Crea una cuenta de aplicación sin almacenar contraseñas en texto plano."""

from getpass import getpass

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.security import hash_password

ALLOWED_ROLES = {"analista", "marketing", "ayuda"}


def main() -> None:
    settings = get_settings()
    name = input("Nombre: ").strip()
    email = input("Correo: ").strip().lower()
    role = input("Rol (analista/marketing/ayuda): ").strip().casefold()
    password = getpass("Contraseña (mínimo 12 caracteres): ")
    confirmation = getpass("Repite la contraseña: ")
    if not name or not email or role not in ALLOWED_ROLES:
        raise SystemExit("Nombre, correo o rol inválido.")
    if len(password) < 12 or password != confirmation:
        raise SystemExit("La contraseña debe tener 12 caracteres y ambas entradas deben coincidir.")

    engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM usuario WHERE lower(email) = lower(:email)"),
                {"email": email},
            ).first()
            if exists:
                raise SystemExit("Ya existe una cuenta con ese correo.")
            connection.execute(
                text("""
                    INSERT INTO usuario (nombre, rol, email, password_hash)
                    VALUES (:name, :role, :email, :password_hash)
                """),
                {
                    "name": name,
                    # Guarda el código estable del rol; la interfaz presenta su nombre traducido.
                    "role": role,
                    "email": email,
                    "password_hash": hash_password(password),
                },
            )
    finally:
        engine.dispose()
    print("Usuario creado. La contraseña no se muestra ni se guarda en texto plano.")


if __name__ == "__main__":
    main()
