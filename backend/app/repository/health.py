"""Database reachability probe used by the readiness route."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class HealthRepository:
    """Checks that the database answers.

    :param session: Database session of the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def ping(self) -> bool:
        """Run ``SELECT 1`` and report whether it succeeded.

        Driver errors are wrapped by SQLAlchemy, but a refused or timed-out connection can
        surface as a plain ``OSError`` or ``TimeoutError``; all of them mean "not reachable".
        Only the exception class is logged: the message can contain the connection URL.

        :return: True if the database answered, False otherwise.
        """
        try:
            await self.db.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            logger.warning("database ping failed", extra={"error": type(exc).__name__})
            return False
        return True
