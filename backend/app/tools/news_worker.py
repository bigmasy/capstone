"""Collect the news digest once, or every day for as long as the process runs.

Usage, from ``backend/``: ``python -m app.tools.news_worker`` keeps running and refreshes the
digest when the last refresh is older than ``NEWS_REFRESH_HOURS`` (24 by default), checking
once an hour; ``python -m app.tools.news_worker --once`` refreshes now and exits. The compose
file runs the first form as the ``news`` service, so the landing page never waits for a feed:
visitors only read what was stored.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta

from app.composition import build_news_service
from app.conf.config import Settings, get_settings
from app.core.logging import configure_logging
from app.database.db import DatabaseSessionManager
from app.services.news import RefreshReport

logger = logging.getLogger(__name__)

# How often a waiting worker looks at the clock; a refresh is due at most this late
CHECK_INTERVAL_SECONDS = 3600.0
# After a run that failed as a whole (the database was down) the next try comes after this
RETRY_SECONDS = 3600.0
EXIT_ALL_FAILED = 1


def seconds_until_due(last: datetime | None, now: datetime, interval: timedelta) -> float:
    """Say how long to wait before the next refresh is due.

    :param last: Time of the last refresh, or None when there never was one.
    :param now: Current time.
    :param interval: Time between refreshes.
    :return: Seconds to wait; zero or less means refresh now.
    """
    if last is None:
        return 0.0
    return (last + interval - now).total_seconds()


async def refresh_once(settings: Settings) -> tuple[RefreshReport, datetime | None]:
    """Refresh the digest in a session of its own.

    :param settings: Application settings.
    :return: What the run did and the time the digest was last refreshed before it.
    """
    manager = DatabaseSessionManager(settings)
    try:
        async with manager.session() as session:
            service = build_news_service(session)
            before = await service.last_refresh()
            return await service.refresh(), before
    finally:
        await manager.close()


async def last_refresh(settings: Settings) -> datetime | None:
    """Read when the digest was last refreshed.

    :param settings: Application settings.
    :return: The time, or None if it never was.
    """
    manager = DatabaseSessionManager(settings)
    try:
        async with manager.session() as session:
            return await build_news_service(session).last_refresh()
    finally:
        await manager.close()


async def run_forever(
    settings: Settings,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    last: Callable[[Settings], Awaitable[datetime | None]] = last_refresh,
    refresh: Callable[[Settings], Awaitable[tuple[RefreshReport, datetime | None]]] = refresh_once,
    rounds: int | None = None,
) -> None:
    """Refresh the digest whenever it is due, for ever.

    A problem of any kind is logged by its class and does not stop the loop: the digest is
    optional, and the next check comes soon.

    :param settings: Application settings.
    :param clock: Source of the current time; replaced in tests.
    :param sleep: Waits for a number of seconds; replaced in tests.
    :param last: Reads the time of the last refresh; replaced in tests.
    :param refresh: Runs one refresh; replaced in tests.
    :param rounds: Stop after this many checks (tests); None means never.
    """
    interval = timedelta(hours=settings.NEWS_REFRESH_HOURS)
    done = 0
    while rounds is None or done < rounds:
        done += 1
        try:
            wait = seconds_until_due(await last(settings), clock(), interval)
            if wait > 0:
                await sleep(min(wait, CHECK_INTERVAL_SECONDS))
                continue
            report, _ = await refresh(settings)
            logger.info(
                "news refreshed: %d added, %d removed, failed sources: %s",
                report.added,
                report.removed,
                ", ".join(report.failed) or "none",
            )
            # A run that read nothing at all is retried sooner than a day later
            if report.failed and report.added == 0:
                await sleep(RETRY_SECONDS)
        except Exception as error:
            logger.warning("news refresh failed (%s)", type(error).__name__)
            await sleep(RETRY_SECONDS)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    :param argv: Arguments without the program name; defaults to ``sys.argv``.
    :return: Process exit code: 0, or 1 when a ``--once`` run could not read a single source.
    """
    parser = argparse.ArgumentParser(prog="python -m app.tools.news_worker", description=__doc__)
    parser.add_argument("--once", action="store_true", help="refresh now and exit")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings)
    if args.once:
        report, _ = asyncio.run(refresh_once(settings))
        sys.stdout.write(
            f"added {report.added}, removed {report.removed}, "
            f"failed: {', '.join(report.failed) or 'none'}\n"
        )
        return EXIT_ALL_FAILED if report.added == 0 and report.failed else 0
    asyncio.run(run_forever(settings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
