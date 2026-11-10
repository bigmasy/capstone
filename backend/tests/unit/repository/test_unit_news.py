from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base, NewsItem
from app.domain.news import NewsEntry
from app.repository.news import KEEP_PER_SOURCE, NewsRepository

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def news(session: AsyncSession) -> NewsRepository:
    return NewsRepository(session)


def entry(n: int, source: str = "s1", age_days: float = 0) -> NewsEntry:
    return NewsEntry(
        source_id=source,
        title=f"Item {n}",
        url=f"https://a.example/{source}/{n}",
        published_at=T0 - timedelta(days=age_days, minutes=n),
    )


async def count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(NewsItem)) or 0


async def test_storing_the_same_items_twice_stores_them_once(
    session: AsyncSession, news: NewsRepository
):
    items = [entry(1), entry(2), entry(2)]

    assert await news.add_new(items, T0) == 2
    assert await news.add_new(items, T0 + timedelta(days=1)) == 0
    assert await count(session) == 2


async def test_the_newest_items_come_first_and_ties_have_a_stable_order(news: NewsRepository):
    same_time = datetime(2026, 11, 1, tzinfo=UTC)
    await news.add_new(
        [
            NewsEntry("s1", "B", "https://a.example/b", same_time),
            NewsEntry("s1", "A", "https://a.example/a", same_time),
            entry(5),
        ],
        T0,
    )

    found = await news.latest(["s1"], 10)

    assert [e.title for e in found] == ["Item 5", "A", "B"]
    assert found[0].published_at.tzinfo is not None


async def test_only_the_asked_sources_are_read_and_the_limit_applies(news: NewsRepository):
    await news.add_new([entry(n, "s1") for n in range(5)] + [entry(1, "s2")], T0)

    assert len(await news.latest(["s1"], 3)) == 3
    assert {e.source_id for e in await news.latest(["s2"], 10)} == {"s2"}
    assert await news.latest([], 10) == []
    assert await news.latest(["s1"], 0) == []


async def test_items_past_the_retention_date_are_removed(
    session: AsyncSession, news: NewsRepository
):
    await news.add_new([entry(1, age_days=1), entry(2, age_days=200)], T0)

    removed = await news.prune(["s1"], T0 - timedelta(days=90))

    assert removed == 1
    assert [e.title for e in await news.latest(["s1"], 10)] == ["Item 1"]


async def test_a_source_keeps_only_its_newest_items(session: AsyncSession, news: NewsRepository):
    total = KEEP_PER_SOURCE + 5
    await news.add_new([entry(n, "s1", age_days=n / 100) for n in range(total)], T0)
    await news.add_new([entry(1, "s2")], T0)

    removed = await news.prune(["s1", "s2"], T0 - timedelta(days=90))

    assert removed == 5
    assert len(await news.latest(["s1"], 1000)) == KEEP_PER_SOURCE
    assert len(await news.latest(["s2"], 10)) == 1
    # The oldest of the source are the ones that went
    kept = {e.title for e in await news.latest(["s1"], 1000)}
    assert "Item 0" in kept
    assert f"Item {total - 1}" not in kept


async def test_the_last_fetch_time_is_the_latest_collection(news: NewsRepository):
    assert await news.last_fetch_time() is None

    await news.add_new([entry(1)], T0)
    await news.add_new([entry(2)], T0 + timedelta(days=1))

    assert await news.last_fetch_time() == T0 + timedelta(days=1)
