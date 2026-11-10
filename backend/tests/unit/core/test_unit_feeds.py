from datetime import UTC, datetime

import pytest

from app.core import feeds
from app.core.feeds import MAX_FEED_BYTES, MAX_ITEMS_PER_FEED, FeedError, parse_feed

RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>x</title>
<item><title>First &amp; best</title><link> https://a.example/1 </link>
<description>About sport</description><pubDate>Tue, 10 Nov 2026 09:38:22 +0200</pubDate></item>
<item><title>No date</title><link>https://a.example/2</link></item>
<item><title>Bad date</title><link>https://a.example/3</link><pubDate>yesterday</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>x</title>
<entry><title>Entry</title><link rel="self" href="https://a.example/self"/>
<link rel="alternate" href="https://a.example/e1"/><summary>S</summary>
<updated>2026-11-09T12:00:00Z</updated></entry></feed>"""


def test_an_rss_feed_is_read_with_dates_in_utc():
    items = parse_feed(RSS)

    assert [i.title for i in items] == ["First & best", "No date", "Bad date"]
    assert items[0].link == "https://a.example/1"
    assert items[0].summary == "About sport"
    assert items[0].published == datetime(2026, 11, 10, 7, 38, 22, tzinfo=UTC)
    assert items[1].published is None
    assert items[2].published is None


def test_an_atom_feed_uses_the_alternate_link_and_the_iso_date():
    (item,) = parse_feed(ATOM)

    assert item.link == "https://a.example/e1"
    assert item.published == datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def test_at_most_a_bounded_number_of_items_is_read():
    body = "".join(
        f"<item><title>{n}</title><link>https://a.example/{n}</link></item>" for n in range(500)
    )
    items = parse_feed(f"<rss><channel>{body}</channel></rss>".encode())

    assert len(items) == MAX_ITEMS_PER_FEED


@pytest.mark.parametrize(
    "document",
    [
        b"not xml at all",
        b"<rss><channel><item></rss>",
        b"<html><body><p>an error page</p></body></html>",
        b"<?xml version='1.0'?><root><item><title>x</title></item></root>",
    ],
)
def test_a_document_that_is_not_a_feed_is_refused(document: bytes):
    with pytest.raises(FeedError):
        parse_feed(document)


def test_a_doctype_is_refused_so_no_entity_can_expand():
    bomb = (
        b'<?xml version="1.0"?>\n'
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>\n'
        b"<rss><channel><item><title>&lol2;</title><link>https://a.example/1</link></item>"
        b"</channel></rss>"
    )
    external = b"""<?xml version="1.0"?>
<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>
<rss><channel><item><title>&x;</title><link>https://a.example/1</link></item></channel></rss>"""

    for document in (bomb, external):
        with pytest.raises(FeedError):
            parse_feed(document)


class FakeResponse:
    def __init__(self, url: str, data: bytes) -> None:
        self.url, self.data = url, data

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, limit: int) -> bytes:
        return self.data[:limit]


def test_only_https_is_fetched():
    with pytest.raises(FeedError):
        feeds._fetch_blocking("http://a.example/feed", ("a.example",))  # noqa: SLF001


def test_a_redirect_to_another_site_is_refused(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        feeds.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse("https://evil.example/feed", b"<rss/>"),
    )

    with pytest.raises(FeedError):
        feeds._fetch_blocking("https://a.example/feed", ("a.example",))  # noqa: SLF001


def test_a_feed_over_the_size_limit_is_refused(monkeypatch: pytest.MonkeyPatch):
    big = b"x" * (MAX_FEED_BYTES + 5)
    monkeypatch.setattr(
        feeds.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse("https://a.example/feed", big),
    )

    with pytest.raises(FeedError):
        feeds._fetch_blocking("https://a.example/feed", ("a.example",))  # noqa: SLF001


def test_a_network_problem_is_reported_by_its_class_only(monkeypatch: pytest.MonkeyPatch):
    def broken(request: object, timeout: float) -> None:
        raise OSError("connection refused to secret-host")

    monkeypatch.setattr(feeds.urllib.request, "urlopen", broken)

    with pytest.raises(FeedError) as caught:
        feeds._fetch_blocking("https://a.example/feed", ("a.example",))  # noqa: SLF001

    assert str(caught.value) == "OSError"


def test_a_good_feed_is_returned_untouched(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        feeds.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse("https://www.a.example/feed", RSS),
    )

    assert feeds._fetch_blocking("https://a.example/feed", ("a.example",)) == RSS  # noqa: SLF001
