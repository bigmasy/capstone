import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = pytest.mark.postgis


@pytest.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    yield engine
    await engine.dispose()


async def test_database_answers(pg_engine: AsyncEngine):
    async with pg_engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


async def test_postgis_extension_is_available(pg_engine: AsyncEngine):
    async with pg_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        version = (await connection.execute(text("SELECT postgis_version()"))).scalar_one()

    assert version


async def test_geography_distance_is_computed(pg_engine: AsyncEngine):
    async with pg_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        metres = (
            await connection.execute(
                text(
                    "SELECT ST_Distance("
                    "ST_MakePoint(30.5234, 50.4501)::geography, "
                    "ST_MakePoint(30.5234, 50.4591)::geography, false)"
                )
            )
        ).scalar_one()

    assert 990 < metres < 1010
