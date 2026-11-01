"""Comprueba el contenido mínimo del instalador limpio final."""

import re
import unittest
from pathlib import Path


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema_wuf_predict_db.sql"


class FinalSchemaTests(unittest.TestCase):
    def test_installer_has_only_the_used_tables_and_audit_name_fields(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        tables = re.findall(r"CREATE\s+TABLE\s+([a-z_]+)", schema, flags=re.IGNORECASE)

        self.assertEqual(len(tables), 20)
        self.assertEqual(len(set(tables)), 20)
        self.assertNotIn("adoptante", tables)
        self.assertNotIn("adopcion", tables)
        self.assertIn("nombre_usuario_generador VARCHAR(100) NOT NULL", schema)
        self.assertIn("nombre_usuario_actor VARCHAR(100) NOT NULL", schema)
