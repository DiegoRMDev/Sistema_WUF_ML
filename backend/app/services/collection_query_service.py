"""Consultas de HU01 separadas de las rutas HTTP."""

from app.domain.collection import CollectionRepositoryPort


class CollectionQueryService:
    def __init__(self, repository: CollectionRepositoryPort) -> None:
        self._repository = repository

    def list_runs(self, limit: int, offset: int) -> list[dict[str, object]]:
        return self._repository.list_runs(limit, offset)

    def get_overview(self) -> dict[str, object] | None:
        return self._repository.latest_completed_run()
