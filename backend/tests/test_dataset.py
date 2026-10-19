"""Casos de aceptación de las etiquetas del Dataset Histórico HU02."""

import unittest
from datetime import date
from pydantic import ValidationError

from app.domain.dataset import classify_cohort_pet, validate_followup_period
from app.api.schemas import DatasetCreateRequest


class DatasetLabelTests(unittest.TestCase):
    def test_available_through_all_captures_remains(self) -> None:
        self.assertEqual(classify_cohort_pet(["disponible", "disponible", "disponible"]),
                         ("permanece", None, 2))

    def test_first_unavailable_state_is_catalog_exit_proxy(self) -> None:
        self.assertEqual(classify_cohort_pet(["disponible", "no_disponible", "no_disponible"]),
                         ("salio_catalogo", "estado_no_disponible", 1))

    def test_absence_in_complete_capture_is_catalog_exit(self) -> None:
        self.assertEqual(classify_cohort_pet(["disponible", None, "disponible"]),
                         ("salio_catalogo", "ausencia_en_captura_completa", 1))

    def test_unpublished_without_conclusive_evidence_is_indeterminate(self) -> None:
        self.assertEqual(classify_cohort_pet(["disponible", "sin_publicar", "disponible"]),
                         ("indeterminada", "estado_sin_evidencia_concluyente", None))

    def test_later_conclusive_exit_after_unpublished_state_is_exit(self) -> None:
        self.assertEqual(classify_cohort_pet(["disponible", "sin_publicar", "no_disponible"]),
                         ("salio_catalogo", "estado_no_disponible", 2))

    def test_baseline_must_be_available(self) -> None:
        with self.assertRaises(ValueError):
            classify_cohort_pet(["no_disponible", "no_disponible"])

    def test_period_request_accepts_ordered_dates(self) -> None:
        request = DatasetCreateRequest(fecha_desde="2026-09-28", fecha_hasta="2026-10-12")
        self.assertEqual(request.fecha_desde, date(2026, 9, 28))

    def test_period_request_rejects_same_or_reversed_dates(self) -> None:
        with self.assertRaises(ValidationError):
            DatasetCreateRequest(fecha_desde="2026-10-12", fecha_hasta="2026-10-12")

    def test_followup_period_requires_three_captures_and_two_weeks(self) -> None:
        self.assertEqual(validate_followup_period(date(2026, 9, 28), date(2026, 10, 12), 3), 2)
        with self.assertRaises(ValueError):
            validate_followup_period(date(2026, 9, 28), date(2026, 10, 12), 2)
        with self.assertRaises(ValueError):
            validate_followup_period(date(2026, 9, 28), date(2026, 10, 5), 3)


if __name__ == "__main__":
    unittest.main()
