import logging

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.repository.health import HealthRepository
from app.services.health import HealthService


class FailingSession:
    def __init__(self, failure: Exception) -> None:
        self.failure = failure

    async def execute(self, *args: object, **kwargs: object) -> None:
        raise self.failure


async def test_ping_succeeds_against_a_live_database(engine: AsyncEngine):
    async with async_sessionmaker(engine)() as session:
        assert await HealthRepository(session).ping() is True


@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("SELECT 1", {}, Exception("secret")),
        ConnectionRefusedError("secret"),
        TimeoutError("secret"),
    ],
)
async def test_ping_reports_failure_and_logs_only_the_class(
    failure: Exception, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.WARNING)
    repository = HealthRepository(FailingSession(failure))  # type: ignore[arg-type]

    assert await repository.ping() is False

    assert "secret" not in caplog.text
    assert type(failure).__name__ in caplog.records[0].error  # type: ignore[attr-defined]


async def test_unrelated_errors_are_not_swallowed():
    repository = HealthRepository(FailingSession(ValueError("bug")))  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        await repository.ping()


async def test_service_returns_the_probe_result():
    class Fake:
        def __init__(self, answer: bool) -> None:
            self.answer = answer

        async def ping(self) -> bool:
            return self.answer

    assert await HealthService(Fake(True)).is_ready() is True  # type: ignore[arg-type]
    assert await HealthService(Fake(False)).is_ready() is False  # type: ignore[arg-type]
