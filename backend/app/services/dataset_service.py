"""Casos de uso de HU02; coordina la API con la persistencia del dataset."""

from datetime import date

from sqlalchemy.orm import Session

from app.infrastructure.dataset_repository import DatasetRepository


class DatasetService:
    def __init__(self, repository: DatasetRepository) -> None:
        self._repository = repository

    @classmethod
    def from_session(cls, session: Session) -> "DatasetService":
        return cls(DatasetRepository(session))

    def list_datasets(self) -> list[dict[str, object]]:
        return self._repository.list_datasets()

    def list_completed_runs(self) -> list[dict[str, object]]:
        return self._repository.list_completed_runs()

    def create_dataset(self, start_date: date, end_date: date) -> int:
        return self._repository.create_from_completed_runs(start_date, end_date)

    def get_dataset(self, dataset_id: int) -> dict[str, object] | None:
        return self._repository.get_dataset(dataset_id)

    def export_csv(self, dataset_id: int) -> bytes | None:
        return self._repository.export_csv(dataset_id)
