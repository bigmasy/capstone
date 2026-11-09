import pytest
from sqlalchemy import text

from app.database.db import DatabaseSessionManager
from app.database.models import NAMING_CONVENTION, Base
from tests.conftest import make_settings


async def test_session_executes_queries():
    manager = DatabaseSessionManager(make_settings())

    async with manager.session() as session:
        value = (await session.execute(text("SELECT 1"))).scalar_one()
    await manager.close()

    assert value == 1


async def test_session_rolls_back_and_reraises():
    manager = DatabaseSessionManager(make_settings())
    rolled_back = []

    with pytest.raises(RuntimeError, match="boom"):
        async with manager.session() as session:
            original = session.rollback

            async def spy() -> None:
                rolled_back.append(True)
                await original()

            session.rollback = spy  # type: ignore[method-assign]
            raise RuntimeError("boom")
    await manager.close()

    assert rolled_back == [True]


async def test_closed_manager_refuses_sessions():
    manager = DatabaseSessionManager(make_settings())
    await manager.close()
    await manager.close()

    with pytest.raises(RuntimeError, match="closed"):
        async with manager.session():
            pass


def test_metadata_uses_the_naming_convention():
    assert Base.metadata.naming_convention == NAMING_CONVENTION
