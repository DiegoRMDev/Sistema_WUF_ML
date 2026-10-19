"""Consultas y persistencia transaccional del Dataset Histórico HU02."""

import csv
import hashlib
import io
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.dataset import classify_cohort_pet, validate_followup_period


class DatasetInputError(ValueError):
    """Los snapshots disponibles no permiten crear un dataset reproducible."""


class DatasetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_datasets(self) -> list[dict[str, object]]:
        rows = self._session.execute(text("""
            SELECT id_dataset, version, fecha_desde, fecha_hasta, nro_registros,
                   origen_etiquetas, version_regla_etiquetado
            FROM dataset_historico ORDER BY id_dataset DESC
        """)).mappings()
        return [dict(row) for row in rows]

    def list_completed_runs(self) -> list[dict[str, object]]:
        """Ofrece solo capturas completas como opciones de periodo en HU02."""
        rows = self._session.execute(text("""
            SELECT id_ejecucion, fecha_captura, semana, perfiles_total
            FROM ejecucion_recoleccion WHERE estado='completada'
            ORDER BY fecha_captura, id_ejecucion
        """)).mappings()
        return [dict(row) for row in rows]

    def create_from_completed_runs(self, start_date: date, end_date: date) -> int:
        """Versiona la cohorte inicial usando el intervalo seleccionado como horizonte."""
        runs = self._session.execute(text("""
            SELECT id_ejecucion, fecha_captura, semana
            FROM ejecucion_recoleccion
            WHERE estado = 'completada'
              AND fecha_captura BETWEEN :start_date AND :end_date
            ORDER BY fecha_captura, id_ejecucion
        """), {"start_date": start_date, "end_date": end_date}).mappings().all()
        try:
            validate_followup_period(start_date, end_date, len(runs))
        except ValueError as exc:
            raise DatasetInputError(str(exc)) from exc
        if len({row["fecha_captura"] for row in runs}) != len(runs):
            raise DatasetInputError("Hay varias capturas completas para una fecha; resuelve el duplicado antes de comparar.")
        if runs[0]["fecha_captura"] != start_date or runs[-1]["fecha_captura"] != end_date:
            raise DatasetInputError("Las fechas inicial y final deben corresponder a capturas completas.")

        run_ids = [int(row["id_ejecucion"]) for row in runs]
        snapshots = self._session.execute(text("""
            SELECT s.id_snapshot, s.id_mascota, s.id_ejecucion, s.sku, s.nombre,
                   s.orden_publicacion, s.estado_detectado, s.especie, s.raza, s.sexo,
                   s.edad_meses, s.edad_estimada, s.tipo_pelaje, s.tamano,
                   s.tamano_estimado, s.nivel_energia, s.condicion_especial,
                   s.condicion_detalle, s.descripcion, s.fecha_publicacion, s.url_perfil,
                   m.id_mascota AS mascota_id
            FROM snapshot_catalogo s JOIN mascota m ON m.id_mascota = s.id_mascota
            WHERE s.id_ejecucion = ANY(CAST(:run_ids AS INTEGER[]))
            ORDER BY s.id_ejecucion, s.id_mascota
        """), {"run_ids": run_ids}).mappings().all()
        if not snapshots:
            raise DatasetInputError("Las capturas completas no contienen snapshots.")

        snapshots_by_pet: dict[int, dict[int, dict[str, object]]] = {}
        for snapshot in snapshots:
            snapshots_by_pet.setdefault(int(snapshot["id_mascota"]), {})[
                int(snapshot["id_ejecucion"])
            ] = dict(snapshot)
        baseline_id = run_ids[0]
        baseline_pets = {
            pet_id: by_run[baseline_id]
            for pet_id, by_run in snapshots_by_pet.items()
            if baseline_id in by_run and by_run[baseline_id]["estado_detectado"] == "disponible"
        }
        if not baseline_pets:
            raise DatasetInputError("La captura inicial no tiene mascotas disponibles para formar la cohorte.")

        start_date: date = runs[0]["fecha_captura"]
        end_date: date = runs[-1]["fecha_captura"]
        # El hash se calcula sobre un CSV canónico construido después de insertar los detalles.
        dataset_id = int(self._session.execute(text("""
            INSERT INTO dataset_historico
                (nro_registros, version, origen_etiquetas, fecha_desde, fecha_hasta,
                 version_regla_etiquetado, hash_sha256)
            VALUES (:count, 'pendiente', 'derivada_catalogo', :start_date, :end_date,
                    'cohorte_horizonte_v2', NULL)
            RETURNING id_dataset
        """), {"count": len(baseline_pets),
              "start_date": start_date, "end_date": end_date}).scalar_one())

        try:
            # La versión deriva del ID generado y permanece única aunque se elimine una versión antigua.
            self._session.execute(text("""
                UPDATE dataset_historico SET version=:version WHERE id_dataset=:dataset_id
            """), {"version": f"v{dataset_id}", "dataset_id": dataset_id})
            self._session.execute(text("""
                INSERT INTO dataset_ejecucion (id_dataset, id_ejecucion)
                SELECT :dataset_id, run_id
                FROM unnest(CAST(:run_ids AS INTEGER[])) AS source(run_id)
            """), {"dataset_id": dataset_id, "run_ids": run_ids})
            self._session.execute(text("""
                INSERT INTO dataset_snapshot (id_dataset, id_snapshot)
                SELECT :dataset_id, snapshot_id
                FROM unnest(CAST(:snapshot_ids AS INTEGER[])) AS source(snapshot_id)
            """), {"dataset_id": dataset_id,
                  "snapshot_ids": [int(row["id_snapshot"]) for row in snapshots]})
            for pet_id, reference in baseline_pets.items():
                states = [
                    snapshots_by_pet.get(pet_id, {}).get(run_id, {}).get("estado_detectado")
                    for run_id in run_ids
                ]
                label, reason, evidence_index = classify_cohort_pet(states)
                result_run_id = run_ids[evidence_index] if evidence_index is not None else None
                result_snapshot = (
                    snapshots_by_pet.get(pet_id, {}).get(result_run_id)
                    if result_run_id is not None else None
                )
                self._session.execute(text("""
                    INSERT INTO dataset_detalle
                        (id_dataset, id_mascota, id_snapshot_referencia,
                         id_ejecucion_resultado, id_snapshot_resultado,
                         etiqueta_catalogo, interpretacion_rf03, motivo_indeterminado)
                    VALUES (:dataset_id, :pet_id, :reference_snapshot, :result_run,
                            :result_snapshot, :label, 'proxy', :reason)
                """), {
                    "dataset_id": dataset_id,
                    "pet_id": pet_id,
                    "reference_snapshot": int(reference["id_snapshot"]),
                    "result_run": result_run_id,
                    "result_snapshot": int(result_snapshot["id_snapshot"]) if result_snapshot else None,
                    "label": label,
                    "reason": reason,
                })
            csv_content = self._csv_bytes(dataset_id)
            self._session.execute(text("""
                UPDATE dataset_historico SET hash_sha256 = :digest WHERE id_dataset = :dataset_id
            """), {"digest": hashlib.sha256(csv_content).hexdigest(), "dataset_id": dataset_id})
            self._session.commit()
            return dataset_id
        except Exception:
            self._session.rollback()
            raise

    def get_dataset(self, dataset_id: int) -> dict[str, object] | None:
        header = self._session.execute(text("""
            SELECT id_dataset, version, fecha_desde, fecha_hasta, nro_registros,
                   origen_etiquetas, version_regla_etiquetado, hash_sha256,
                   (SELECT COUNT(*) FROM dataset_detalle d WHERE d.id_dataset=h.id_dataset
                    AND etiqueta_catalogo='permanece') AS permanece,
                   (SELECT COUNT(*) FROM dataset_detalle d WHERE d.id_dataset=h.id_dataset
                    AND etiqueta_catalogo='salio_catalogo') AS salio,
                   (SELECT COUNT(*) FROM dataset_detalle d WHERE d.id_dataset=h.id_dataset
                    AND etiqueta_catalogo='indeterminada') AS indeterminada
            FROM dataset_historico h WHERE id_dataset=:dataset_id
        """), {"dataset_id": dataset_id}).mappings().first()
        if header is None:
            return None
        runs = self._session.execute(text("""
            SELECT r.id_ejecucion, r.semana, r.fecha_captura
            FROM dataset_ejecucion de JOIN ejecucion_recoleccion r USING (id_ejecucion)
            WHERE de.id_dataset=:dataset_id ORDER BY r.fecha_captura, r.id_ejecucion
        """), {"dataset_id": dataset_id}).mappings().all()
        observations = self._session.execute(text("""
            SELECT d.id_mascota, d.etiqueta_catalogo, ref.sku, ref.nombre,
                   ref.orden_publicacion, ref.especie, ref.raza, ref.sexo,
                   ref.edad_meses, ref.edad_estimada, ref.tipo_pelaje, ref.tamano,
                   ref.tamano_estimado, ref.nivel_energia, ref.condicion_especial,
                   ref.condicion_detalle, ref.descripcion, ref.fecha_publicacion,
                   ref.url_perfil, r.id_ejecucion, s.estado_detectado
            FROM dataset_detalle d
            JOIN snapshot_catalogo ref ON ref.id_snapshot=d.id_snapshot_referencia
            JOIN dataset_ejecucion de ON de.id_dataset=d.id_dataset
            JOIN ejecucion_recoleccion r ON r.id_ejecucion=de.id_ejecucion
            LEFT JOIN snapshot_catalogo s ON s.id_mascota=d.id_mascota AND s.id_ejecucion=r.id_ejecucion
            WHERE d.id_dataset=:dataset_id
            ORDER BY ref.orden_publicacion DESC, d.id_mascota, r.fecha_captura
        """), {"dataset_id": dataset_id}).mappings().all()
        pets: dict[int, dict[str, object]] = {}
        for row in observations:
            pet_id = int(row["id_mascota"])
            pet = pets.setdefault(pet_id, {
                "id_mascota": pet_id, "sku": row["sku"], "nombre": row["nombre"],
                "orden_publicacion": row["orden_publicacion"], "etiqueta": row["etiqueta_catalogo"],
                "estados": {},
            })
            pet["estados"][int(row["id_ejecucion"])] = row["estado_detectado"]
        # Los detalles enriquecidos se consultan una vez para el CSV de entrenamiento.
        details = self._session.execute(text("""
            SELECT d.etiqueta_catalogo, d.motivo_indeterminado, ref.*
            FROM dataset_detalle d JOIN snapshot_catalogo ref
              ON ref.id_snapshot=d.id_snapshot_referencia
            WHERE d.id_dataset=:dataset_id ORDER BY ref.orden_publicacion DESC, d.id_mascota
        """), {"dataset_id": dataset_id}).mappings().all()
        return {"dataset": dict(header), "runs": [dict(run) for run in runs],
                "pets": list(pets.values()), "details": [dict(row) for row in details]}

    def _csv_bytes(self, dataset_id: int) -> bytes:
        metadata = self._session.execute(text("""
            SELECT h.version, h.origen_etiquetas, h.fecha_desde, h.fecha_hasta,
                   h.fecha_generacion, h.nro_registros, h.version_regla_etiquetado,
                   (SELECT COUNT(*) FROM dataset_detalle d WHERE d.id_dataset=h.id_dataset
                    AND d.etiqueta_catalogo='permanece') AS permanece,
                   (SELECT COUNT(*) FROM dataset_detalle d WHERE d.id_dataset=h.id_dataset
                    AND d.etiqueta_catalogo='salio_catalogo') AS salio_catalogo,
                   (SELECT COUNT(*) FROM dataset_detalle d WHERE d.id_dataset=h.id_dataset
                    AND d.etiqueta_catalogo='indeterminada') AS indeterminada
            FROM dataset_historico h WHERE h.id_dataset=:dataset_id
        """), {"dataset_id": dataset_id}).mappings().one()
        runs = self._session.execute(text("""
            SELECT r.id_ejecucion, r.semana, r.fecha_captura
            FROM dataset_ejecucion de JOIN ejecucion_recoleccion r USING (id_ejecucion)
            WHERE de.id_dataset=:dataset_id ORDER BY r.fecha_captura, r.id_ejecucion
        """), {"dataset_id": dataset_id}).mappings().all()
        rows = self._session.execute(text("""
            SELECT ref.sku, ref.nombre, ref.especie, ref.raza, ref.sexo, ref.edad_meses,
                   ref.edad_estimada, ref.tipo_pelaje, ref.tamano, ref.tamano_estimado,
                   ref.nivel_energia, ref.condicion_especial, ref.condicion_detalle,
                   ref.descripcion, ref.orden_publicacion, ref.fecha_publicacion,
                   d.etiqueta_catalogo, d.motivo_indeterminado
            FROM dataset_detalle d JOIN snapshot_catalogo ref
              ON ref.id_snapshot=d.id_snapshot_referencia
            WHERE d.id_dataset=:dataset_id
            ORDER BY ref.orden_publicacion DESC, d.id_mascota
        """), {"dataset_id": dataset_id}).mappings().all()
        state_rows = self._session.execute(text("""
            SELECT s.id_mascota, s.id_ejecucion, s.estado_detectado
            FROM dataset_snapshot ds JOIN snapshot_catalogo s USING (id_snapshot)
            WHERE ds.id_dataset=:dataset_id
        """), {"dataset_id": dataset_id}).mappings().all()
        state_map = {(int(row["id_mascota"]), int(row["id_ejecucion"])): row["estado_detectado"]
                     for row in state_rows}
        output = io.StringIO(newline="")
        metadata_fields = ["dataset_version", "origen_etiquetas", "fecha_desde", "fecha_hasta",
                           "fecha_generacion", "nro_registros", "permanece", "salio_catalogo",
                           "indeterminada", "version_regla_etiquetado"]
        feature_fields = list(rows[0].keys()) if rows else ["sku", "nombre", "etiqueta_catalogo"]
        state_fields = [f"estado_semana_{run['semana']}_{run['fecha_captura']}" for run in runs]
        fields = metadata_fields + feature_fields + state_fields
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            # Evita que una hoja de cálculo ejecute texto aportado como fórmula.
            item = {
                key: ("'" + value if isinstance(value, str) and value and value[0] in "=+-@\t\r" else value)
                for key, value in dict(row).items()
            }
            item.update({"dataset_version": metadata["version"]})
            item.update({key: metadata[key] for key in metadata_fields if key != "dataset_version"})
            pet_id = int(self._session.execute(text("""
                SELECT id_mascota FROM mascota WHERE sku=:sku ORDER BY id_mascota LIMIT 1
            """), {"sku": item["sku"]}).scalar_one())
            for run, field in zip(runs, state_fields, strict=True):
                item[field] = state_map.get((pet_id, int(run["id_ejecucion"])), "")
            writer.writerow(item)
        return output.getvalue().encode("utf-8-sig")

    def export_csv(self, dataset_id: int) -> bytes | None:
        exists = self._session.execute(text(
            "SELECT 1 FROM dataset_historico WHERE id_dataset=:dataset_id"
        ), {"dataset_id": dataset_id}).scalar_one_or_none()
        return self._csv_bytes(dataset_id) if exists else None
