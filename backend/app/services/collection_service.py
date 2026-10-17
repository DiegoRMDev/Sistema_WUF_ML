"""Caso de uso HU01 para capturar catálogo, vigencia y snapshots."""

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, time
from typing import Any

from app.domain.catalog import CatalogSource
from app.domain.collection import CollectionRepositoryPort


class CollectionService:
    def __init__(
        self,
        source: CatalogSource,
        repository: CollectionRepositoryPort,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC).replace(tzinfo=None),
    ) -> None:
        self._source = source
        self._repository = repository
        self._clock = clock

    def execute(self, actor_id: int | None, execution_type: str = "manual") -> dict[str, Any]:
        started_at = self._clock()
        capture_date = self._source.capture_date
        week = capture_date.isocalendar().week
        run_id = self._repository.start_run(
            actor_id=actor_id,
            started_at=started_at,
            capture_date=capture_date,
            week=week,
            execution_type=execution_type,
            source_name=self._source.source_name,
            source_reference=self._source.source_reference,
        )

        try:
            batch = self._source.fetch_pets()
            persisted, rejected = self._repository.persist_capture(
                run_id=run_id,
                pets=batch.pets,
                captured_at=datetime.combine(capture_date, time.min),
                week=week,
            )
            finished_at = self._clock()
            rejected += batch.rejected_profiles
            has_issues = bool(batch.rejection_summary) or rejected > 0
            status = "completada" if not has_issues else ("parcial" if persisted else "fallida")
            rejection_summary = Counter(batch.rejection_summary)
            if persisted < len(batch.pets):
                rejection_summary["rechazo_de_persistencia"] += len(batch.pets) - persisted
            error_message = None
            if rejection_summary:
                details = ", ".join(f"{key}={count}" for key, count in sorted(rejection_summary.items()))
                error_message = f"Incidencias de captura; perfiles rechazados: {rejected}. {details}"[:1000]
            self._repository.finish_run(
                run_id=run_id,
                finished_at=finished_at,
                status=status,
                total=batch.total_profiles,
                available=batch.available,
                unavailable=batch.unavailable,
                unpublished=batch.unpublished,
                error_message=error_message,
            )
            return {
                "id_ejecucion": run_id,
                "fuente_datos": self._source.source_name,
                "referencia_fuente": self._source.source_reference,
                "fecha_captura": capture_date,
                "fecha_inicio": started_at,
                "fecha_fin": finished_at,
                "semana": week,
                "perfiles_total": batch.total_profiles,
                "perfiles_persistidos": persisted,
                "perfiles_rechazados": rejected,
                "perfiles_disponibles": batch.available,
                "perfiles_no_disponibles": batch.unavailable,
                "perfiles_sin_publicar": batch.unpublished,
                "estado": status,
                "mensaje_error": error_message,
            }
        except Exception:
            self._repository.finish_run(
                run_id=run_id,
                finished_at=self._clock(),
                status="fallida",
                total=0,
                available=0,
                unavailable=0,
                unpublished=0,
                error_message="No se pudo completar la consulta o persistencia del catálogo.",
            )
            raise

