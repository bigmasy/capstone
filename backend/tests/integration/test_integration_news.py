"""The news digest over HTTP: public, bounded and free of anything but the stored items."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.domain.news import NewsEntry
from app.repository.news import NewsRepository

API = "/api/v1"
T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


async def store(client: httpx.AsyncClient, entries: list[NewsEntry]) -> None:
    app = client._transport.app  # type: ignore[attr-defined]  # noqa: SLF001
    override = app.dependency_overrides[get_db]
    async for session in override():
        assert isinstance(session, AsyncSession)
        await NewsRepository(session).add_new(entries, T0)


def entry(n: int, source: str, minutes: int = 0) -> NewsEntry:
    return NewsEntry(
        source_id=source,
        title=f"Title {n}",
        url=f"https://www.paralympic.org/n/{n}",
        published_at=T0 - timedelta(minutes=minutes + n),
    )


async def test_the_digest_is_public_and_has_a_column_per_category(client: httpx.AsyncClient):
    response = await client.get(f"{API}/news")

    assert response.status_code == 200
    assert [c["id"] for c in response.json()["columns"]] == ["world", "ukraine", "veterans"]
    assert all(c["items"] == [] for c in response.json()["columns"])


async def test_stored_items_are_returned_newest_first_with_the_source_name(
    client: httpx.AsyncClient,
):
    await store(client, [entry(2, "ipc"), entry(1, "ipc"), entry(3, "move-united")])

    columns = (await client.get(f"{API}/news")).json()["columns"]

    world = columns[0]["items"]
    assert [i["title"] for i in world] == ["Title 1", "Title 2", "Title 3"] or [
        i["title"] for i in world
    ] == ["Title 3", "Title 2", "Title 1"][::-1]
    assert {i["source"] for i in world} == {"Міжнародний паралімпійський комітет", "Move United"}
    assert set(world[0]) == {"title", "url", "source", "published_at"}


async def test_the_limit_is_applied_per_column_and_validated(client: httpx.AsyncClient):
    await store(client, [entry(n, "ipc") for n in range(1, 9)])

    limited = (await client.get(f"{API}/news?limit=3")).json()["columns"][0]["items"]

    assert len(limited) == 3
    for bad in ("0", "21", "-1", "x"):
        assert (await client.get(f"{API}/news?limit={bad}")).status_code == 422


async def test_nothing_but_links_titles_and_names_is_exposed(client: httpx.AsyncClient):
    await store(client, [entry(1, "ipc")])

    body = (await client.get(f"{API}/news")).text

    for private in ("fetched_at", "source_id", "password", "email", "token"):
        assert private not in body
