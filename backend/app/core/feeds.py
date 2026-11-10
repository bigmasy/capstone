"""Fetching and reading RSS and Atom feeds.

A feed comes from a third party, so it is treated as hostile input: only the fixed addresses of
``app.domain.news.SOURCES`` are fetched, over https, with a timeout and a size limit, and the XML
is parsed with ``defusedxml``, which refuses doctype declarations, entities and the other tricks
that turn a small document into a denial of service or a file read.
"""

import asyncio
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from defusedxml import ElementTree as SafeElementTree  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

USER_AGENT = "Poruch/1.0 (news digest for a thesis project)"
FETCH_TIMEOUT_SECONDS = 15
MAX_FEED_BYTES = 3 * 1024 * 1024
MAX_ITEMS_PER_FEED = 100

_ATOM = "{http://www.w3.org/2005/Atom}"


class FeedError(Exception):
    """A feed could not be fetched or read; the text names only the kind of problem."""


@dataclass(frozen=True, slots=True)
class RawItem:
    """An item as found in a feed, before any cleaning.

    :param title: Title text.
    :param link: Link text.
    :param summary: Summary text, possibly empty.
    :param published: Publication time (UTC), or None when absent or unreadable.
    """

    title: str
    link: str
    summary: str
    published: datetime | None


def _as_utc(moment: datetime) -> datetime:
    """Return a timestamp as timezone-aware UTC; one without a zone is taken as UTC."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _parse_date(text: str) -> datetime | None:
    """Read an RFC 822 or an ISO 8601 date; None when it is neither."""
    text = text.strip()
    if not text:
        return None
    try:
        return _as_utc(parsedate_to_datetime(text))
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def parse_feed(data: bytes) -> list[RawItem]:
    """Read the items of an RSS 2.0 or Atom feed.

    :param data: The document.
    :raises FeedError: If it is not well-formed XML, uses a doctype or an entity, or is neither
        RSS nor Atom.
    :return: At most ``MAX_ITEMS_PER_FEED`` items in document order.
    """
    try:
        root = SafeElementTree.fromstring(data, forbid_dtd=True)
    except (SafeElementTree.ParseError, DefusedXmlException, ValueError):
        raise FeedError("the document is not safe, well-formed XML") from None
    items: list[RawItem] = []
    for element in root.iter("item"):
        items.append(
            RawItem(
                title=element.findtext("title") or "",
                link=(element.findtext("link") or "").strip(),
                summary=element.findtext("description") or "",
                published=_parse_date(element.findtext("pubDate") or ""),
            )
        )
    for entry in root.iter(f"{_ATOM}entry"):
        href = ""
        for link in entry.findall(f"{_ATOM}link"):
            if link.get("rel", "alternate") == "alternate" and link.get("href"):
                href = link.get("href", "")
                break
        items.append(
            RawItem(
                title=entry.findtext(f"{_ATOM}title") or "",
                link=href.strip(),
                summary=entry.findtext(f"{_ATOM}summary") or "",
                published=_parse_date(
                    entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated") or ""
                ),
            )
        )
    if root.tag not in {
        "rss",
        "RDF",
        f"{_ATOM}feed",
        "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF",
    }:
        raise FeedError("the document is neither RSS nor Atom")
    return items[:MAX_ITEMS_PER_FEED]


def _fetch_blocking(url: str, hosts: tuple[str, ...]) -> bytes:
    """Download a feed synchronously, within the limits."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise FeedError("only https feeds are fetched")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
            final = (urlsplit(response.geturl()).hostname or "").lower()
            if not any(final == host or final.endswith("." + host) for host in hosts):
                raise FeedError("the feed redirected to another site")
            data: bytes = response.read(MAX_FEED_BYTES + 1)
    except FeedError:
        raise
    except (OSError, ValueError) as error:
        raise FeedError(type(error).__name__) from None
    if len(data) > MAX_FEED_BYTES:
        raise FeedError("the feed is larger than the limit")
    return data


async def fetch_feed(url: str, hosts: tuple[str, ...]) -> bytes:
    """Download a feed in a worker thread.

    :param url: Fixed https address of the feed.
    :param hosts: Hosts the address and any redirect may lead to.
    :raises FeedError: On any problem; the text never holds the address.
    :return: The raw document, at most ``MAX_FEED_BYTES`` long.
    """
    return await asyncio.to_thread(_fetch_blocking, url, hosts)
