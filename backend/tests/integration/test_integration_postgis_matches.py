"""GET /api/v1/matches on PostgreSQL/PostGIS, served by the ST_DWithin candidate source."""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.db import get_db
from app.main import create_app
from tests.conftest import make_settings
from tests.integration.helpers import make_profile_body, sign_up
from tests.integration.test_integration_postgis_candidates import (  # noqa: F401
    migrated_url,
    pg_engine,
)

pytestmark = pytest.mark.postgis

URL = "/api/v1/matches"


@pytest.fixture
async def pg_client(
    pg_engine: AsyncEngine,  # noqa: F811
) -> AsyncIterator[httpx.AsyncClient]:
    app: FastAPI = create_app(make_settings(DB_URL=os.environ["TEST_DATABASE_URL"]))
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def add(client: httpx.AsyncClient, **overrides: object):
    actor = await sign_up(client)
    response = await client.put(
        "/api/v1/profiles/me", json=make_profile_body(**overrides), headers=actor.headers
    )
    assert response.status_code == 200, response.text
    return actor


async def test_the_feed_on_postgis_orders_by_score_and_applies_the_radius(
    pg_client: httpx.AsyncClient,
):
    me = await add(pg_client, display_name="Me")
    await add(pg_client, display_name="Near")
    await add(pg_client, display_name="Mid", latitude=50.53)
    await add(pg_client, display_name="Far", latitude=50.60)
    await add(pg_client, display_name="Hidden", is_visible=False)
    await add(pg_client, display_name="Elsewhere", latitude=48.5, longitude=35.0)

    wide = (await pg_client.get(URL, headers=me.headers)).json()
    narrow = (await pg_client.get(URL, params={"radius_km": 10}, headers=me.headers)).json()

    assert [i["display_name"] for i in wide["items"]] == ["Near", "Mid", "Far"]
    assert [i["display_name"] for i in narrow["items"]] == ["Near", "Mid"]
    assert [i["distance_band"] for i in wide["items"]] == ["under 5 km", "5–10 km", "10–25 km"]
    totals = [i["breakdown"]["total"] for i in wide["items"]]
    assert totals == sorted(totals, reverse=True)


async def test_the_feed_on_postgis_shields_functional_data_and_hides_the_rest(
    pg_client: httpx.AsyncClient,
):
    vision = {"category": "vision", "level": 4}
    hearing = {"category": "hearing", "level": 4}
    endurance = {"category": "endurance", "level": 0}
    me = await add(pg_client, capabilities=[vision, hearing])
    await add(pg_client, display_name="Probe", capabilities=[{**vision, "level": 0}, endurance])
    await add(pg_client, display_name="Match", capabilities=[vision, hearing])

    response = await pg_client.get(URL, headers=me.headers)

    items = {i["display_name"]: i for i in response.json()["items"]}
    assert items["Probe"]["breakdown"]["functional"] == "medium"
    assert items["Match"]["breakdown"]["functional"] == "high"
    for forbidden in ("capabilities", "equipment", "latitude", "longitude", "vision", "hearing"):
        assert forbidden not in response.text


async def test_a_caller_without_a_profile_gets_404_on_postgis(pg_client: httpx.AsyncClient):
    actor = await sign_up(pg_client)

    response = await pg_client.get(URL, headers=actor.headers)

    assert response.status_code == 404
