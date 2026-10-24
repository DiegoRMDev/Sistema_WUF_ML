"""Consultas PostgreSQL para el entrenamiento y las evaluaciones HU04."""

import json
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class ConsistencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def training_timeline(self) -> list[dict[str, Any]]:
        """Devuelve snapshots completos y huecos de catálogo para medir permanencia."""
        rows = self._session.execute(text("""
            WITH completed_runs AS (
                SELECT id_ejecucion, fecha_captura::date AS fecha_captura
                FROM ejecucion_recoleccion
                WHERE estado = 'completada'
            ), known_pets AS (
                SELECT DISTINCT id_mascota, sku
                FROM snapshot_catalogo
            )
            SELECT run.id_ejecucion, run.fecha_captura,
                   pet.id_mascota, pet.sku,
                   snapshot.id_snapshot, snapshot.nombre,
                   snapshot.fecha_publicacion, snapshot.estado_detectado
            FROM completed_runs AS run
            CROSS JOIN known_pets AS pet
            LEFT JOIN snapshot_catalogo AS snapshot
              ON snapshot.id_ejecucion = run.id_ejecucion
             AND snapshot.id_mascota = pet.id_mascota
            ORDER BY run.fecha_captura, run.id_ejecucion, pet.sku
        """)).mappings().all()
        return [dict(row) for row in rows]

    def latest_completed_run(self) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            SELECT id_ejecucion, fecha_captura::date AS fecha_captura, semana
            FROM ejecucion_recoleccion
            WHERE estado = 'completada'
            ORDER BY fecha_captura DESC, id_ejecucion DESC
            LIMIT 1
        """)).mappings().first()
        return dict(row) if row else None

    def insert_model(
        self,
        *,
        actor_id: int,
        execution_id: int,
        metrics: dict[str, float],
        confusion: list[list[int]],
        importance: list[dict[str, float | str]],
        metadata: dict[str, Any],
        rules: str,
    ) -> tuple[int, str]:
        """Crea una versión provisional y la marca como la evaluación vigente."""
        self._session.execute(text("SELECT pg_advisory_xact_lock(1479021124)"))
        self._session.execute(text("UPDATE modelo_consistencia SET es_vigente = FALSE WHERE es_vigente"))
        row = self._session.execute(text("""
            INSERT INTO modelo_consistencia (
                version, algoritmo, fuente_etiquetas, id_ejecucion_referencia,
                id_usuario, fecha_entrenamiento, accuracy_score, f1_macro_score, nro_registros_entrenamiento,
                nro_registros_prueba, matriz_confusion, importancia_variables,
                reglas_arbol, metadatos_entrenamiento, artefacto_ruta,
                artefacto_sha256, es_vigente
            )
            VALUES (
                'v' || (COALESCE((SELECT MAX(SUBSTRING(version FROM 2)::INTEGER)
                                  FROM modelo_consistencia), 0) + 1)::TEXT,
                'DecisionTreeClassifier', :label_source, :execution_id,
                :actor_id, (CURRENT_TIMESTAMP AT TIME ZONE 'America/Lima'),
                :accuracy, :f1_macro, :train_count, :test_count,
                CAST(:confusion AS JSONB), CAST(:importance AS JSONB), :rules,
                CAST(:metadata AS JSONB), 'pending', :placeholder_hash, TRUE
            )
            RETURNING id_modelo_consistencia, version
        """), {
            "actor_id": actor_id,
            "execution_id": execution_id,
            "label_source": metadata["version_regla_revision"],
            "accuracy": metrics["accuracy"],
            "f1_macro": metrics["f1_macro"],
            "train_count": metadata["nro_registros_entrenamiento"],
            "test_count": metadata["nro_registros_prueba"],
            "confusion": json.dumps(confusion),
            "importance": json.dumps(importance),
            "rules": rules,
            "metadata": json.dumps(metadata),
            "placeholder_hash": "0" * 64,
        }).mappings().one()
        return int(row["id_modelo_consistencia"]), str(row["version"])

    def set_artifact_reference(self, model_id: int, filename: str, digest: str) -> None:
        self._session.execute(text("""
            UPDATE modelo_consistencia
            SET artefacto_ruta = :filename, artefacto_sha256 = :digest
            WHERE id_modelo_consistencia = :model_id
        """), {"model_id": model_id, "filename": filename, "digest": digest})

    def insert_assessments(
        self,
        model_id: int,
        execution_id: int,
        captured_on: date,
        assessments: list[dict[str, Any]],
    ) -> None:
        """Guarda la evidencia usada para cada perfil evaluado en la última captura."""
        for item in assessments:
            self._session.execute(text("""
                INSERT INTO evaluacion_consistencia (
                    id_modelo_consistencia, id_mascota, id_snapshot, id_ejecucion,
                    fecha_evaluacion, nivel_riesgo, fuente_etiqueta, justificacion,
                    indicadores
                ) VALUES (
                    :model_id, :pet_id, :snapshot_id, :execution_id,
                    :captured_on, :risk, :label_source, :explanation,
                    CAST(:features AS JSONB)
                )
            """), {
                "model_id": model_id,
                "pet_id": item["id_mascota"],
                "snapshot_id": item["id_snapshot"],
                "execution_id": execution_id,
                "captured_on": captured_on,
                "risk": item["nivel_riesgo"],
                "label_source": item["indicadores"]["origen"],
                "explanation": item["justificacion"],
                "features": json.dumps(item["indicadores"]),
            })

    def latest_report(self) -> dict[str, Any] | None:
        model_id = self._session.execute(text("""
            SELECT id_modelo_consistencia
            FROM modelo_consistencia
            WHERE es_vigente = TRUE
            ORDER BY id_modelo_consistencia DESC
            LIMIT 1
        """)).scalar_one_or_none()
        return self.report_for_model(int(model_id)) if model_id is not None else None

    def report_for_model(self, model_id: int) -> dict[str, Any] | None:
        row = self._session.execute(text("""
            SELECT id_modelo_consistencia, version, algoritmo, fuente_etiquetas,
                   fecha_entrenamiento, accuracy_score, f1_macro_score,
                   nro_registros_entrenamiento, nro_registros_prueba,
                   matriz_confusion, importancia_variables, reglas_arbol,
                   metadatos_entrenamiento, id_ejecucion_referencia, es_vigente,
                   artefacto_ruta, TRIM(artefacto_sha256) AS artefacto_sha256
            FROM modelo_consistencia
            WHERE id_modelo_consistencia = :model_id
        """), {"model_id": model_id}).mappings().first()
        if row is None:
            return None
        report = dict(row)
        items = self._session.execute(text("""
            SELECT assessment.nivel_riesgo, assessment.justificacion,
                   assessment.indicadores, pet.sku, snapshot.nombre,
                   assessment.fecha_evaluacion, run.semana,
                   assessment.id_mascota
            FROM evaluacion_consistencia AS assessment
            JOIN mascota AS pet ON pet.id_mascota = assessment.id_mascota
            JOIN snapshot_catalogo AS snapshot ON snapshot.id_snapshot = assessment.id_snapshot
            JOIN ejecucion_recoleccion AS run ON run.id_ejecucion = assessment.id_ejecucion
            WHERE assessment.id_modelo_consistencia = :model_id
            ORDER BY CASE assessment.nivel_riesgo WHEN 'alto' THEN 0
                      WHEN 'medio' THEN 1 ELSE 2 END, pet.sku
        """), {"model_id": report["id_modelo_consistencia"]}).mappings().all()
        report["items"] = [dict(item) for item in items]
        return report

    def model_history(self) -> list[dict[str, Any]]:
        rows = self._session.execute(text("""
            SELECT id_modelo_consistencia, version, fecha_entrenamiento,
                   accuracy_score, f1_macro_score, nro_registros_entrenamiento,
                   nro_registros_prueba, id_ejecucion_referencia, es_vigente
            FROM modelo_consistencia
            ORDER BY id_modelo_consistencia DESC
            LIMIT 30
        """)).mappings().all()
        return [dict(row) for row in rows]
