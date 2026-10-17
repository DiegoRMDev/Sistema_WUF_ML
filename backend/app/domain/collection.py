"""Puerto de persistencia para el caso de uso de captura."""

from datetime import date, datetime
from typing import Protocol

from app.domain.catalog import CatalogPet


class CollectionRepositoryPort(Protocol):
    def start_run(
        self,
        actor_id: int | None,
        started_at: datetime,
        capture_date: date,
        week: int,
        execution_type: str,
        source_name: str,
        source_reference: str | None,
    ) -> int: ...

    def persist_capture(
        self, run_id: int, pets: list[CatalogPet], captured_at: datetime, week: int
    ) -> tuple[int, int]: ...

    def finish_run(
        self,
        run_id: int,
        finished_at: datetime,
        status: str,
        total: int,
        available: int,
        unavailable: int,
        unpublished: int,
        error_message: str | None,
    ) -> None: ...

    def list_runs(self, limit: int, offset: int) -> list[dict[str, object]]: ...

    def latest_completed_run(self) -> dict[str, object] | None: ...
