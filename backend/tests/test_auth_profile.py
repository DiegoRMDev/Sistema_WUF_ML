"""Pruebas estándar de edición de perfil sin PostgreSQL ni dependencias extra."""

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.api.schemas import PasswordChangeRequest, ProfileUpdateRequest
from app.api.v1.auth import change_password, update_me
from app.core.security import hash_password, verify_password


class AccountProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.session = Session(self.engine)
        self.session.execute(text("""
            CREATE TABLE usuario (
                id_usuario INTEGER PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                rol VARCHAR(20) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL
            )
        """))
        self.session.execute(text("""
            INSERT INTO usuario (id_usuario, nombre, rol, email, password_hash)
            VALUES (1, 'Analista de prueba', 'analista', 'analista@example.com', :password_hash)
        """), {"password_hash": hash_password("clave-inicial-123")})
        self.session.commit()
        self.user = CurrentUser(
            id_usuario=1,
            nombre="Analista de prueba",
            email="analista@example.com",
            rol="analista",
        )

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_name_update_is_trimmed_and_persisted(self) -> None:
        response = update_me(ProfileUpdateRequest(nombre="  Analista Nuevo  "), self.user, self.session)

        self.assertEqual(response.nombre, "Analista Nuevo")
        stored_name = self.session.execute(
            text("SELECT nombre FROM usuario WHERE id_usuario=1")
        ).scalar_one()
        self.assertEqual(stored_name, "Analista Nuevo")

    def test_blank_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProfileUpdateRequest(nombre="   ")

    def test_password_change_checks_old_password_and_saves_argon_hash(self) -> None:
        payload = PasswordChangeRequest(
            current_password="clave-inicial-123",
            new_password="clave-nueva-segura-456",
            confirm_password="clave-nueva-segura-456",
        )

        response = change_password(payload, self.user, self.session)

        stored_hash = self.session.execute(
            text("SELECT password_hash FROM usuario WHERE id_usuario=1")
        ).scalar_one()
        self.assertEqual(response.status_code, 204)
        self.assertTrue(verify_password("clave-nueva-segura-456", stored_hash))
        self.assertFalse(verify_password("clave-inicial-123", stored_hash))

    def test_wrong_old_password_does_not_change_the_hash(self) -> None:
        payload = PasswordChangeRequest(
            current_password="incorrecta",
            new_password="clave-nueva-segura-456",
            confirm_password="clave-nueva-segura-456",
        )
        old_hash = self.session.execute(
            text("SELECT password_hash FROM usuario WHERE id_usuario=1")
        ).scalar_one()

        with self.assertRaises(HTTPException) as error:
            change_password(payload, self.user, self.session)

        new_hash = self.session.execute(
            text("SELECT password_hash FROM usuario WHERE id_usuario=1")
        ).scalar_one()
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(new_hash, old_hash)

    def test_password_confirmation_must_match_and_new_password_must_differ(self) -> None:
        with self.assertRaises(ValueError):
            PasswordChangeRequest(
                current_password="clave-inicial-123",
                new_password="clave-nueva-segura-456",
                confirm_password="otra-clave-segura-456",
            )
        with self.assertRaises(ValueError):
            PasswordChangeRequest(
                current_password="clave-inicial-123",
                new_password="clave-inicial-123",
                confirm_password="clave-inicial-123",
            )


if __name__ == "__main__":
    unittest.main()
