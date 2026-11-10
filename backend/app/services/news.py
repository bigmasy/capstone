"""The news digest: collecting items from the fixed sources and reading them back."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.feeds import FeedError, RawItem, fetch_feed, parse_feed
from app.domain.news import (
    CATEGORIES,
    SOURCES,
    FeedSource,
    NewsColumn,
    NewsEntry,
    clean_title,
    is_on_topic,
    link_allowed,
)
from app.repository.news import NewsRepository

logger = logging.getLogger(__name__)

# Items older than this are not kept: the digest is about what is current
RETENTION = timedelta(days=90)
# A date this far ahead is a mistake of the feed, not news from the future
_FUTURE_TOLERANCE = timedelta(hours=1)

Fetch = Callable[[str, tuple[str, ...]], Awaitable[bytes]]


def _utc_now() -> datetime:
    """Return the current time as timezone-aware UTC."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RefreshReport:
    """What one collection run did.

    :param added: Items stored.
    :param failed: Codes of the sources that could not be read this time.
    :param removed: Old items removed.
    """

    added: int
    failed: tuple[str, ...]
    removed: int


def _entries_of(source: FeedSource, raw: list[RawItem], now: datetime) -> list[NewsEntry]:
    """Clean the items of one feed and keep the acceptable ones."""
    entries: list[NewsEntry] = []
    for item in raw:
        title = clean_title(item.title)
        if not title or not link_allowed(item.link, source.hosts):
            continue
        if source.filtered and not is_on_topic(title, clean_title(item.summary), source.topic):
            continue
        published = item.published or now
        if published > now + _FUTURE_TOLERANCE:
            published = now
        entries.append(
            NewsEntry(source_id=source.id, title=title, url=item.link, published_at=published)
        )
    return entries


def _take_turns(pool: list[NewsEntry], limit: int) -> list[NewsEntry]:
    """Pick items so that the sources of a column alternate, each newest first.

    :param pool: Items of one column, newest first.
    :param limit: How many to pick.
    :return: At most ``limit`` items, the newest of each source in turn, then ordered by date.
    """
    queues: dict[str, list[NewsEntry]] = {}
    for item in pool:
        queues.setdefault(item.source_id, []).append(item)
    chosen: list[NewsEntry] = []
    while len(chosen) < limit and any(queues.values()):
        for queue in queues.values():
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
    return sorted(chosen, key=lambda item: (-item.published_at.timestamp(), item.url))


class NewsService:
    """Collects the digest and serves it.

    :param news: Repository of items.
    :param fetch: Downloads a feed; replaced in tests.
    :param clock: Source of the current time; replaced in tests.
    """

    def __init__(
        self,
        news: NewsRepository,
        fetch: Fetch = fetch_feed,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Keep the collaborators."""
        self.news = news
        self.fetch = fetch
        self.clock = clock

    async def refresh(self) -> RefreshReport:
        """Collect every source once.

        A source that cannot be fetched or read is skipped and reported, and the others are
        still collected. Only the source code and the class of the problem are logged.

        :return: Counts of what was added and removed and the sources that failed.
        """
        now = self.clock()
        added = 0
        failed: list[str] = []
        for source in SOURCES:
            try:
                data = await self.fetch(source.feed_url, source.hosts)
                entries = _entries_of(source, parse_feed(data), now)
            except FeedError as error:
                logger.warning("news source %s skipped (%s)", source.id, error)
                failed.append(source.id)
                continue
            added += await self.news.add_new(entries, now)
        removed = await self.news.prune([s.id for s in SOURCES], now - RETENTION)
        return RefreshReport(added=added, failed=tuple(failed), removed=removed)

    async def digest(self, per_category: int) -> list[NewsColumn]:
        """Read the newest items of every category.

        :param per_category: Maximum number of items in a category.
        :return: One column per category, in the fixed order, possibly empty.
        """
        names = {source.id: source.name for source in SOURCES}
        columns: list[NewsColumn] = []
        for category in CATEGORIES:
            ids = [source.id for source in SOURCES if source.category == category]
            # Newest first would let the busiest source fill the column; the sources take turns
            pool = await self.news.latest(ids, per_category * len(ids) * 2)
            entries = _take_turns(pool, per_category)
            columns.append(
                NewsColumn(id=category, items=tuple((e, names[e.source_id]) for e in entries))
            )
        return columns

    async def last_refresh(self) -> datetime | None:
        """Return when the digest was last refreshed.

        :return: The time, or None if it never was.
        """
        return await self.news.last_fetch_time()
