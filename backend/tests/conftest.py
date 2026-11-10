"""Shared fixtures: application factory on in-memory SQLite and an async HTTP client."""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.conf.config import Settings, get_settings
from app.database.db import enable_sqlite_foreign_keys, get_db
from app.database.models import Base
from app.main import create_app

TEST_SECRET = "t" * 40


def make_settings(**overrides: object) -> Settings:
    """Build test settings that ignore any local ``.env`` file."""
    values: dict[str, object] = {
        "ENV": "test",
        "DB_URL": "sqlite+aiosqlite:///:memory:",
        "JWT_SECRET": TEST_SECRET,
        "CORS_ORIGINS": ["http://localhost:5173"],
        # Cheap Argon2 parameters keep the suite fast; production uses the defaults.
        "ARGON2_TIME_COST": 1,
        "ARGON2_MEMORY_COST_KIB": 8,
        "ARGON2_PARALLELISM": 1,
        # Messages stay in memory, where the tests read the confirmation link
        "MAIL_BACKEND": "memory",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked ``postgis`` unless ``TEST_DATABASE_URL`` is set."""
    if os.environ.get("TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL is not set")
    for item in items:
        if "postgis" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove application variables from the environment and reset the settings cache."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    """Settings for the ``test`` environment."""
    return make_settings()


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """In-memory async SQLite engine shared by all connections of one test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    enable_sqlite_foreign_keys(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
def app(settings: Settings, engine: AsyncEngine) -> FastAPI:
    """Application whose ``get_db`` dependency is bound to the test engine."""
    application = create_app(settings)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
async def schema(engine: AsyncEngine) -> None:
    """Create the tables on the test engine (migrations are tested separately)."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture
async def client(app: FastAPI, schema: None) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client talking to the application in-process."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
