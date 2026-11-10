import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.services.news import RefreshReport
from app.tools.news_worker import (
    CHECK_INTERVAL_SECONDS,
    RETRY_SECONDS,
    run_forever,
    seconds_until_due,
)
from tests.conftest import make_settings

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
DAY = timedelta(hours=24)


def test_a_refresh_is_due_when_there_never_was_one():
    assert seconds_until_due(None, NOW, DAY) == 0


def test_the_wait_is_what_is_left_of_the_interval():
    assert seconds_until_due(NOW - timedelta(hours=20), NOW, DAY) == 4 * 3600
    assert seconds_until_due(NOW - DAY, NOW, DAY) == 0
    assert seconds_until_due(NOW - timedelta(days=3), NOW, DAY) < 0


class Script:
    """Stands in for the clock, the database and the network of one worker."""

    def __init__(self, last: datetime | None, report: RefreshReport | Exception) -> None:
        self.last, self.report = last, report
        self.sleeps: list[float] = []
        self.refreshes = 0

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    async def read_last(self, settings: object) -> datetime | None:
        return self.last

    async def refresh(self, settings: object) -> tuple[RefreshReport, datetime | None]:
        self.refreshes += 1
        if isinstance(self.report, Exception):
            raise self.report
        self.last = NOW
        return self.report, None


async def run(script: Script, rounds: int) -> None:
    await run_forever(
        make_settings(),
        clock=lambda: NOW,
        sleep=script.sleep,
        last=script.read_last,
        refresh=script.refresh,
        rounds=rounds,
    )


async def test_it_refreshes_at_once_when_nothing_was_collected_yet():
    script = Script(None, RefreshReport(added=3, failed=(), removed=0))

    await run(script, 2)

    assert script.refreshes == 1
    # After the refresh the next check finds the digest fresh and waits, at most an hour
    assert script.sleeps == [CHECK_INTERVAL_SECONDS]


async def test_it_waits_while_the_digest_is_fresh():
    script = Script(NOW - timedelta(hours=1), RefreshReport(0, (), 0))

    await run(script, 3)

    assert script.refreshes == 0
    assert script.sleeps == [CHECK_INTERVAL_SECONDS] * 3


async def test_it_refreshes_once_the_day_is_over():
    script = Script(NOW - timedelta(hours=25), RefreshReport(added=1, failed=(), removed=0))

    await run(script, 1)

    assert script.refreshes == 1


async def test_a_run_that_read_nothing_is_retried_sooner_than_a_day():
    script = Script(None, RefreshReport(added=0, failed=("ipc", "suspilne"), removed=0))

    await run(script, 1)

    assert script.sleeps == [RETRY_SECONDS]


async def test_a_crash_is_logged_by_its_class_and_does_not_stop_the_loop(
    caplog: pytest.LogCaptureFixture,
):
    script = Script(None, RuntimeError("database password is hunter2"))

    with caplog.at_level(logging.WARNING):
        await run(script, 2)

    assert script.refreshes == 2
    assert script.sleeps == [RETRY_SECONDS, RETRY_SECONDS]
    assert "RuntimeError" in caplog.text
    assert "hunter2" not in caplog.text
