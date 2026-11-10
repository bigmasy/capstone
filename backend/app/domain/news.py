"""Adaptive-sport news: the fixed list of sources and the rules every item has to pass.

The sources are written down here and nowhere else, so the application never fetches an address
that came from outside. Everything an item carries (a title, a link, a date) comes from a third
party, so it is cleaned and checked before it is stored: the title is plain text of a bounded
length, the link is an http(s) address on the host of the source it came from, and for feeds
about everything the item has to be about adaptive sport or veterans' sport. Only the standard
library is used.
"""

import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

Category = Literal["world", "ukraine", "veterans"]
# What a general feed is checked against: sport of people with disabilities and of veterans, or the
# wider support of veterans (rehabilitation, prostheses), for the feed of a military publisher
Topic = Literal["sport", "support"]
CATEGORIES: tuple[Category, ...] = ("world", "ukraine", "veterans")

TITLE_MAX_LENGTH = 200
URL_MAX_LENGTH = 1000

_TAG = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"\s+")
# An item of a general feed is kept only when it is about adaptive sport, the Paralympic
# movement, the Invictus Games, or veterans together with sport. The patterns are stems, so they
# cover the Ukrainian word forms.
_TOPIC = re.compile(
    r"адаптивн\w*\s+(?:спорт|фізичн|тренув)|паралімп|дефлімп|параспорт|нескорен|invictus"
    r"|ветеран\w*[^.]{0,80}(?:спорт|змаган|турнір|тренув)"
    r"|(?:спорт|змаган|турнір|тренув)\w*[^.]{0,80}ветеран"
    r"|(?:людей|осіб|особи|люди)\s+з\s+інвалідністю[^.]{0,80}(?:спорт|змаган|тренув)"
    r"|протез\w*[^.]{0,80}(?:спорт|біг|плав|тренув)",
    re.IGNORECASE,
)
_SUPPORT = re.compile(
    r"ветеран|реабілітац|протез|адаптивн|нескорен|паралімп|invictus", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class FeedSource:
    """One publisher whose news feed is collected.

    :param id: Short stable code stored with each item.
    :param name: Name shown next to an item.
    :param category: Column of the landing page the items go to.
    :param feed_url: Address of the RSS or Atom feed.
    :param hosts: Hosts a link of this source may point to (the host or a subdomain of one).
    :param filtered: Whether the feed is about everything, so each item is checked for the topic.
    :param topic: Which topic an item has to match when the feed is filtered.
    """

    id: str
    name: str
    category: Category
    feed_url: str
    hosts: tuple[str, ...]
    filtered: bool
    topic: Topic = "sport"


SOURCES: tuple[FeedSource, ...] = (
    FeedSource(
        id="ipc",
        name="Міжнародний паралімпійський комітет",
        category="world",
        feed_url="https://www.paralympic.org/rss.xml",
        hosts=("paralympic.org",),
        filtered=False,
    ),
    FeedSource(
        id="move-united",
        name="Move United",
        category="world",
        feed_url="https://www.moveunitedsport.org/feed",
        hosts=("moveunitedsport.org",),
        filtered=False,
    ),
    FeedSource(
        id="suspilne",
        name="Суспільне",
        category="ukraine",
        feed_url="https://suspilne.media/rss/all.rss",
        hosts=("suspilne.media",),
        filtered=True,
    ),
    FeedSource(
        id="ukrinform-sport",
        name="Укрінформ",
        category="ukraine",
        feed_url="https://www.ukrinform.ua/rss/rubric-sports",
        hosts=("ukrinform.ua",),
        filtered=True,
    ),
    FeedSource(
        id="ukrinform-society",
        name="Укрінформ",
        category="ukraine",
        feed_url="https://www.ukrinform.ua/rss/rubric-society",
        hosts=("ukrinform.ua",),
        filtered=True,
    ),
    FeedSource(
        id="armyinform",
        name="АрміяInform",
        category="veterans",
        feed_url="https://www.armyinform.com.ua/feed/",
        hosts=("armyinform.com.ua",),
        filtered=True,
        topic="support",
    ),
)


@dataclass(frozen=True, slots=True)
class NewsEntry:
    """A cleaned item ready for storage.

    :param source_id: Code of the source.
    :param title: Plain-text title.
    :param url: Link to the original article.
    :param published_at: Publication time (UTC) as the source gave it, or the time of collection.
    """

    source_id: str
    title: str
    url: str
    published_at: datetime


def clean_title(raw: str) -> str:
    """Turn a title from a feed into plain text of a bounded length.

    Tags are dropped, entities are decoded, runs of whitespace become one space, and a title
    over the limit is cut at a word and ends with an ellipsis. The result is rendered as text,
    never as markup.

    :param raw: Title as the feed gave it.
    :return: Plain text, possibly empty.
    """
    text = html.unescape(_TAG.sub(" ", html.unescape(raw)))
    text = _SPACES.sub(" ", _TAG.sub(" ", text)).strip()
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    cut = text[: TITLE_MAX_LENGTH - 1].rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    return cut + "…"


def link_allowed(url: str, hosts: tuple[str, ...]) -> bool:
    """Tell whether a link may be stored for a source.

    The link has to be a plain http(s) address without credentials, within the length limit,
    on the host of the source or one of its subdomains. A feed therefore cannot point readers at
    another site, a script or a file.

    :param url: Link from the feed.
    :param hosts: Hosts allowed for the source.
    :return: True when the link is acceptable.
    """
    if not url or len(url) > URL_MAX_LENGTH or any(ord(char) < 32 for char in url):
        return False
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        return False
    host = (parts.hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in hosts)


def is_on_topic(title: str, summary: str = "", topic: Topic = "sport") -> bool:
    """Tell whether an item of a general feed is about the topic of its source.

    :param title: Cleaned title.
    :param summary: Cleaned summary, if the feed has one.
    :param topic: ``sport`` for adaptive and veterans' sport, ``support`` for the wider support
        of veterans.
    :return: True when the title or the summary matches one of the topic patterns.
    """
    pattern = _SUPPORT if topic == "support" else _TOPIC
    return pattern.search(title) is not None or pattern.search(summary) is not None


@dataclass(frozen=True, slots=True)
class NewsColumn:
    """The newest items of one category, each with the display name of its publisher.

    :param id: Category code.
    :param items: Pairs of an item and the name of its source.
    """

    id: Category
    items: tuple[tuple[NewsEntry, str], ...]
