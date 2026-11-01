"""Validación de la segmentación completa y anotación posterior de HU06."""

import unittest

from app.domain.profile_clustering import project_profile_clusters, train_profile_clusters


class ProfileClusteringTests(unittest.TestCase):
    def setUp(self) -> None:
        # El conjunto incluye mascotas que cumplen y que no cumplen los criterios HU06.
        self.profiles = []
        for index in range(12):
            senior_or_large = index >= 6
            self.profiles.append({
                "id_snapshot": index + 1,
                "sku": f"WUF{index + 1:04d}",
                "nombre": f"Mascota {index + 1}",
                "edad_meses": 120 + index if senior_or_large else 12 + index,
                "edad_estimada": index % 2 == 0,
                "tamano": "grande" if senior_or_large else "pequeno",
                "tamano_estimado": False,
                "nivel_energia": "bajo" if senior_or_large else "alto",
                "condicion_especial": index in (8, 10),
            })

    def test_trains_on_entire_available_cohort_and_summarizes_criteria(self) -> None:
        result = train_profile_clusters(
            self.profiles, cluster_count=2, seed=42, n_init=20,
        )

        self.assertEqual(len(result["profiles"]), 12)
        self.assertEqual(sum(row["cantidad_perfiles"] for row in result["cluster_summaries"]), 12)
        self.assertEqual(result["parameters"]["cohort_scope"], "all_available_v1")
        self.assertLess(
            sum(row["perfiles_con_atributos_desfavorecidos"] for row in result["cluster_summaries"]),
            12,
        )
        self.assertTrue(all("numero_segmento" in item for item in result["profiles"]))

    def test_projection_includes_profiles_without_disadvantaged_criteria(self) -> None:
        result = train_profile_clusters(
            self.profiles, cluster_count=2, seed=42, n_init=20,
        )
        plot = project_profile_clusters(result["estimator"], self.profiles)

        self.assertEqual(len(plot["points"]), len(self.profiles))
        self.assertTrue(any(not point["atributos_desfavorecidos"] for point in plot["points"]))
        self.assertTrue(all(point["numero_segmento"] in (1, 2) for point in plot["points"]))


if __name__ == "__main__":
    unittest.main()
