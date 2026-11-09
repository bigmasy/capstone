"""Readiness scenario."""

from app.repository.health import HealthRepository


class HealthService:
    """Reports whether the application can serve requests that need the database.

    :param health: Repository that probes the database.
    """

    def __init__(self, health: HealthRepository) -> None:
        """Keep the collaborator."""
        self.health = health

    async def is_ready(self) -> bool:
        """Tell whether the database is reachable.

        :return: True when the application is ready to serve requests.
        """
        return await self.health.ping()
