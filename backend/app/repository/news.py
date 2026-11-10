"""Database access for the news digest."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import NewsItem
from app.domain.news import NewsEntry
from app.repository.users import as_utc

# The newest items kept for each source; older ones are removed when the digest is refreshed
KEEP_PER_SOURCE = 60


class NewsRepository:
    """All database operations on collected news items.

    :param session: Database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def add_new(self, entries: list[NewsEntry], fetched_at: datetime) -> int:
        """Store the items whose address is not stored yet.

        :param entries: Cleaned items; duplicates inside the list are stored once.
        :param fetched_at: Time of collection.
        :return: How many items were stored.
        """
        urls = {entry.url for entry in entries}
        if not urls:
            return 0
        known = set(
            (await self.db.execute(select(NewsItem.url).where(NewsItem.url.in_(urls)))).scalars()
        )
        added: dict[str, NewsEntry] = {e.url: e for e in entries if e.url not in known}
        for entry in added.values():
            self.db.add(
                NewsItem(
                    source_id=entry.source_id,
                    title=entry.title,
                    url=entry.url,
                    published_at=entry.published_at,
                    fetched_at=fetched_at,
                )
            )
        await self.db.commit()
        return len(added)

    async def prune(self, source_ids: list[str], older_than: datetime) -> int:
        """Remove old items: those published before a date, and those beyond the newest few.

        :param source_ids: Sources to tidy.
        :param older_than: Items published before this instant go.
        :return: How many items were removed.
        """
        old = await self.db.execute(delete(NewsItem).where(NewsItem.published_at < older_than))
        count = int(cast(CursorResult[Any], old).rowcount or 0)
        for source_id in source_ids:
            keep = (
                select(NewsItem.id)
                .where(NewsItem.source_id == source_id)
                .order_by(NewsItem.published_at.desc())
                .limit(KEEP_PER_SOURCE)
            )
            extra = await self.db.execute(
                delete(NewsItem).where(NewsItem.source_id == source_id, NewsItem.id.not_in(keep))
            )
            count += int(cast(CursorResult[Any], extra).rowcount or 0)
        await self.db.commit()
        return count

    async def latest(self, source_ids: list[str], limit: int) -> list[NewsEntry]:
        """Return the newest items of a group of sources.

        :param source_ids: Sources to read.
        :param limit: Maximum number of items.
        :return: Items, newest first; ties are broken by address so the order is stable.
        """
        if not source_ids or limit <= 0:
            return []
        result = await self.db.execute(
            select(NewsItem)
            .where(NewsItem.source_id.in_(source_ids))
            .order_by(NewsItem.published_at.desc(), NewsItem.url)
            .limit(limit)
        )
        return [
            NewsEntry(
                source_id=row.source_id,
                title=row.title,
                url=row.url,
                published_at=as_utc(row.published_at),
            )
            for row in result.scalars()
        ]

    async def last_fetch_time(self) -> datetime | None:
        """Return when the digest was last refreshed.

        :return: The latest collection time (UTC), or None when nothing was ever stored.
        """
        moment = (await self.db.execute(select(func.max(NewsItem.fetched_at)))).scalar_one_or_none()
        return None if moment is None else as_utc(moment)
