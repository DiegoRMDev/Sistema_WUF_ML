"""Pruebas del conteo y la validación por fila de CSV HU01."""

import csv
import io
import unittest

from app.core.config import Settings
from app.domain.catalog import CatalogAlreadyImported, CatalogSourceError
from app.infrastructure.csv_catalog_source import CsvCatalogSource

HEADERS = [
    "sku", "nombre", "especie", "raza", "sexo", "edad_meses", "edad_estimada",
    "tipo_pelaje", "tamano", "tamano_estimado", "nivel_energia", "condicion_especial",
    "condicion_detalle", "descripcion", "orden_publicacion", "estado_publicado",
    "fecha_publicacion", "url_perfil", "etiquetas",
]


def make_row(**overrides: str) -> dict[str, str]:
    row = {
        "sku": "DOG-0001", "nombre": "Luna", "especie": "perro", "raza": "Mestiza",
        "sexo": "H", "edad_meses": "24", "edad_estimada": "false", "tipo_pelaje": "corto",
        "tamano": "mediano", "tamano_estimado": "false", "nivel_energia": "medio",
        "condicion_especial": "false", "condicion_detalle": "", "descripcion": "",
        "orden_publicacion": "1", "estado_publicado": "disponible",
        "fecha_publicacion": "2026-10-01", "url_perfil": "https://wuf.pe/perfil/DOG-0001",
        "etiquetas": "",
    }
    row.update(overrides)
    return row


def encode_rows(*rows: dict[str, str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


class CsvCatalogSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            database_url="postgresql+psycopg://test:test@localhost/test",
            jwt_secret="x" * 40,
        )

    def source(self, *rows: dict[str, str]) -> CsvCatalogSource:
        return CsvCatalogSource(self.settings, "captura_2026-10-12.csv", encode_rows(*rows), set())

    def test_counts_a_valid_profile_and_one_rejected_row_with_multiple_invalid_fields(self) -> None:
        source = self.source(
            make_row(),
            make_row(sku="DOG-0002", sexo="X", edad_meses="-1"),
        )

        batch = source.fetch_pets()

        self.assertEqual(batch.total_profiles, 2)
        self.assertEqual(batch.rejected_profiles, 1)
        self.assertEqual(len(batch.pets), 1)
        self.assertGreaterEqual(sum(batch.rejection_summary.values()), 2)

    def test_counts_duplicate_sku_as_one_rejected_row(self) -> None:
        source = self.source(make_row(), make_row(nombre="Otro nombre"))

        batch = source.fetch_pets()

        self.assertEqual(batch.total_profiles, 2)
        self.assertEqual(batch.rejected_profiles, 1)
        self.assertEqual(batch.rejection_summary, {"sku_duplicado": 1})

    def test_counts_all_valid_rows(self) -> None:
        source = self.source(make_row(), make_row(sku="DOG-0002"))

        batch = source.fetch_pets()

        self.assertEqual(batch.total_profiles, 2)
        self.assertEqual(batch.rejected_profiles, 0)
        self.assertEqual(len(batch.pets), 2)

    def test_rejects_a_filename_already_imported(self) -> None:
        with self.assertRaises(CatalogAlreadyImported):
            CsvCatalogSource(
                self.settings, "captura_2026-10-12.csv", encode_rows(make_row()), {"captura_2026-10-12.csv"}
            )

    def test_rejects_a_csv_without_valid_profiles(self) -> None:
        source = self.source(make_row(sexo="X", edad_meses="-1"))

        with self.assertRaises(CatalogSourceError):
            source.fetch_pets()


if __name__ == "__main__":
    unittest.main()
