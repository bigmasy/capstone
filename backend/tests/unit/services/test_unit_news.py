from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.feeds import FeedError
from app.database.models import Base
from app.domain.news import SOURCES
from app.repository.news import NewsRepository
from app.services.news import NewsService

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.moment = T0

    def __call__(self) -> datetime:
        return self.moment


def rss(*items: tuple[str, str, str, str]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{link}</link><description>{d}</description>"
        f"<pubDate>{date}</pubDate></item>"
        for t, link, d, date in items
    )
    return f"<rss><channel>{body}</channel></rss>".encode()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def clock() -> Clock:
    return Clock()


def make_service(
    session: AsyncSession, clock: Clock, feeds: dict[str, bytes | Exception]
) -> NewsService:
    async def fetch(url: str, hosts: tuple[str, ...]) -> bytes:
        outcome = feeds.get(url, FeedError("down"))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return NewsService(NewsRepository(session), fetch, clock)


def url_of(source_id: str) -> str:
    return next(s.feed_url for s in SOURCES if s.id == source_id)


DATE = "Tue, 10 Nov 2026 09:00:00 +0000"


async def test_a_feed_about_adaptive_sport_is_stored_whole(session: AsyncSession, clock: Clock):
    feeds = {url_of("ipc"): rss(("Meet in Brescia", "https://www.paralympic.org/n/1", "", DATE))}
    service = make_service(session, clock, feeds)

    report = await service.refresh()

    assert report.added == 1
    columns = {c.id: c for c in await service.digest(6)}
    ((entry, source),) = columns["world"].items
    assert entry.title == "Meet in Brescia"
    assert source == "Міжнародний паралімпійський комітет"
    assert columns["ukraine"].items == ()


async def test_a_general_feed_keeps_only_items_on_topic(session: AsyncSession, clock: Clock):
    feeds = {
        url_of("suspilne"): rss(
            ("Політика: переговори", "https://suspilne.media/1", "", DATE),
            ("Паралімпійці отримають премії", "https://suspilne.media/2", "", DATE),
            ("Новини дня", "https://suspilne.media/3", "Змагання для ветеранів, спорт", DATE),
        )
    }
    service = make_service(session, clock, feeds)

    await service.refresh()

    titles = [e.title for e, _ in (await service.digest(6))[1].items]
    assert sorted(titles) == ["Новини дня", "Паралімпійці отримають премії"]


async def test_links_to_other_sites_are_dropped(session: AsyncSession, clock: Clock):
    feeds = {
        url_of("ipc"): rss(
            ("Good", "https://www.paralympic.org/n/1", "", DATE),
            ("Elsewhere", "https://evil.example/n/2", "", DATE),
            ("Script", "javascript:alert(1)", "", DATE),
        )
    }

    await make_service(session, clock, feeds).refresh()

    titles = [e.title for e, _ in (await make_service(session, clock, {}).digest(6))[0].items]
    assert titles == ["Good"]


async def test_a_source_that_fails_does_not_stop_the_others(
    session: AsyncSession, clock: Clock, caplog: pytest.LogCaptureFixture
):
    feeds = {
        url_of("ipc"): FeedError("TimeoutError"),
        url_of("move-united"): rss(
            ("Wheelchair league", "https://moveunitedsport.org/a", "", DATE)
        ),
    }
    service = make_service(session, clock, feeds)

    report = await service.refresh()

    assert report.added == 1
    assert "ipc" in report.failed
    assert "move-united" not in report.failed
    # The log names the source and the kind of problem, never an address
    assert "https://" not in caplog.text


async def test_refreshing_twice_stores_nothing_twice(session: AsyncSession, clock: Clock):
    feeds = {url_of("ipc"): rss(("Meet", "https://www.paralympic.org/n/1", "", DATE))}
    service = make_service(session, clock, feeds)

    first = await service.refresh()
    clock.moment = T0 + timedelta(days=1)
    second = await service.refresh()

    assert (first.added, second.added) == (1, 0)


async def test_a_date_far_in_the_future_is_taken_as_now_and_a_missing_one_too(
    session: AsyncSession, clock: Clock
):
    feeds = {
        url_of("ipc"): rss(
            ("Future", "https://www.paralympic.org/n/1", "", "Tue, 10 Nov 2030 09:00:00 +0000"),
            ("Undated", "https://www.paralympic.org/n/2", "", ""),
        )
    }
    service = make_service(session, clock, feeds)

    await service.refresh()

    items = (await service.digest(6))[0].items
    assert {e.published_at for e, _ in items} == {T0}


async def test_old_items_are_dropped_by_the_refresh(session: AsyncSession, clock: Clock):
    feeds = {
        url_of("ipc"): rss(
            ("Ancient", "https://www.paralympic.org/n/1", "", "Tue, 10 Nov 2020 09:00:00 +0000")
        )
    }
    service = make_service(session, clock, feeds)

    report = await service.refresh()

    assert report.removed == 1
    assert (await service.digest(6))[0].items == ()


async def test_the_digest_has_one_column_per_category_in_order(session: AsyncSession, clock: Clock):
    columns = await make_service(session, clock, {}).digest(6)

    assert [c.id for c in columns] == ["world", "ukraine", "veterans"]
    assert all(c.items == () for c in columns)


async def test_the_sources_of_a_column_take_turns_instead_of_the_busiest_filling_it(
    session: AsyncSession, clock: Clock
):
    ipc = [
        (
            f"IPC {n}",
            f"https://www.paralympic.org/n/{n}",
            "",
            f"Tue, 10 Nov 2026 0{9 - n}:00:00 +0000",
        )
        for n in range(6)
    ]
    older = [
        (
            "Wheelchair league",
            "https://moveunitedsport.org/a",
            "",
            "Mon, 02 Nov 2026 09:00:00 +0000",
        )
    ]
    feeds = {url_of("ipc"): rss(*ipc), url_of("move-united"): rss(*older)}
    service = make_service(session, clock, feeds)

    await service.refresh()

    titles = [e.title for e, _ in (await service.digest(4))[0].items]
    assert "Wheelchair league" in titles
    assert len(titles) == 4


async def test_a_military_feed_is_checked_against_the_wider_support_topic(
    session: AsyncSession, clock: Clock
):
    feeds = {
        url_of("armyinform"): rss(
            (
                "У Києві відкрили центр реабілітації для військових",
                "https://www.armyinform.com.ua/1",
                "",
                DATE,
            ),
            ("Сводка з фронту", "https://www.armyinform.com.ua/2", "", DATE),
        )
    }
    service = make_service(session, clock, feeds)

    await service.refresh()

    titles = [e.title for e, _ in (await service.digest(6))[2].items]
    assert titles == ["У Києві відкрили центр реабілітації для військових"]
