"""Async engine, session factory and the ``get_db`` dependency."""

import contextlib
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.conf.config import Settings


def enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """Switch on foreign key enforcement for every SQLite connection of an engine.

    SQLite ignores foreign keys (and therefore ON DELETE CASCADE) unless asked per connection;
    PostgreSQL always enforces them. Without this, deleting an account on SQLite would leave
    its profile and capabilities behind. Does nothing for other databases.

    :param engine: Engine to configure.
    """
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _enable(dbapi_connection: Any, _record: Any) -> None:
        """Run the pragma on a fresh connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class DatabaseSessionManager:
    """Owns an ``AsyncEngine`` and an ``async_sessionmaker`` built from settings.

    Nothing is created at import time: the application factory builds one manager per
    application and disposes it on shutdown.

    :param settings: Application settings; only ``DB_URL`` is used.
    """

    def __init__(self, settings: Settings) -> None:
        """Build the engine and the session factory."""
        url = settings.DB_URL.get_secret_value()
        kwargs: dict[str, object] = {}
        if url.startswith("sqlite") and ":memory:" in url:
            # An in-memory SQLite database lives per connection; share a single one.
            kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        engine = create_async_engine(url, **kwargs)
        enable_sqlite_foreign_keys(engine)
        self._engine: AsyncEngine | None = engine
        self._session_maker: async_sessionmaker[AsyncSession] | None = async_sessionmaker(
            bind=engine, autoflush=False, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        """Return the engine.

        :raises RuntimeError: If the manager was already closed.
        :return: The async engine.
        """
        if self._engine is None:
            raise RuntimeError("Database session manager is closed")
        return self._engine

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a session that is rolled back on error and always closed.

        :raises RuntimeError: If the manager was already closed.
        :raises Exception: Whatever the body raised, re-raised after the rollback.
        :return: An async context manager yielding the session.
        """
        if self._session_maker is None:
            raise RuntimeError("Database session manager is closed")
        session = self._session_maker()
        try:
            yield session
        except BaseException:
            # Any failure, including domain errors raised by the request, must not leave a
            # half-done transaction behind.
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """Dispose the engine; safe to call twice."""
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._session_maker = None


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a session of the running application.

    The manager is stored on ``app.state`` by the lifespan of ``create_app``. Tests replace this
    dependency through ``app.dependency_overrides``.

    :param request: Current request, used to reach ``app.state``.
    :return: An async iterator yielding one session per request.
    """
    manager: DatabaseSessionManager = request.app.state.db
    async with manager.session() as session:
        yield session


# Lets the API layer ask for a session without importing SQLAlchemy itself.
DbSession = Annotated[AsyncSession, Depends(get_db)]
