"""The owner's choice of how coarse the stored area is."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.models import Profile
from app.domain.privacy import AreaPrecision, coarsen
from tests.integration.helpers import make_profile_body, sign_up, sign_up_with_profile

POINT = (50.4501, 30.5234)


async def stored_area(engine: AsyncEngine) -> tuple[float, float, str]:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                select(Profile.area_lat, Profile.area_lon, Profile.area_precision)
            )
        ).one()
    return row.area_lat, row.area_lon, str(row.area_precision.value)


def cell(precision: AreaPrecision) -> tuple[float, float]:
    found = coarsen(*POINT, precision)
    return found.latitude, found.longitude


async def test_a_new_profile_uses_the_default_grid(client: httpx.AsyncClient, engine: AsyncEngine):
    _, profile = await sign_up_with_profile(client)

    assert profile["area_precision"] == "4km"
    assert await stored_area(engine) == (*cell(AreaPrecision.KM_4), "4km")


@pytest.mark.parametrize("precision", list(AreaPrecision))
async def test_the_chosen_grid_is_applied_to_the_location(
    client: httpx.AsyncClient, engine: AsyncEngine, precision: AreaPrecision
):
    actor = await sign_up(client)

    response = await client.put(
        "/api/v1/profiles/me",
        headers=actor.headers,
        json=make_profile_body(area_precision=precision.value),
    )

    assert response.status_code == 200
    assert response.json()["area_precision"] == precision.value
    assert await stored_area(engine) == (*cell(precision), precision.value)


async def test_a_coarser_grid_without_a_location_coarsens_the_stored_area(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor = await sign_up(client)
    await client.put(
        "/api/v1/profiles/me", headers=actor.headers, json=make_profile_body(area_precision="1km")
    )
    body = make_profile_body(area_precision="place")
    del body["latitude"], body["longitude"]

    response = await client.put("/api/v1/profiles/me", headers=actor.headers, json=body)

    assert response.json()["area_precision"] == "place"
    assert await stored_area(engine) == (*cell(AreaPrecision.PLACE), "place")


async def test_a_finer_grid_without_a_location_changes_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, _ = await sign_up_with_profile(client)
    body = make_profile_body(area_precision="1km")
    del body["latitude"], body["longitude"]

    response = await client.put("/api/v1/profiles/me", headers=actor.headers, json=body)

    assert response.status_code == 200
    assert response.json()["area_precision"] == "4km"
    assert await stored_area(engine) == (*cell(AreaPrecision.KM_4), "4km")


async def test_a_save_without_the_field_keeps_the_stored_grid(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor = await sign_up(client)
    await client.put(
        "/api/v1/profiles/me", headers=actor.headers, json=make_profile_body(area_precision="2km")
    )

    again = await client.put(
        "/api/v1/profiles/me", headers=actor.headers, json=make_profile_body(display_name="Ira")
    )

    assert again.json()["area_precision"] == "2km"
    assert await stored_area(engine) == (*cell(AreaPrecision.KM_2), "2km")


async def test_an_unknown_grid_is_rejected(client: httpx.AsyncClient):
    actor = await sign_up(client)

    response = await client.put(
        "/api/v1/profiles/me",
        headers=actor.headers,
        json=make_profile_body(area_precision="100m"),
    )

    assert response.status_code == 422


async def test_other_people_never_learn_the_grid(client: httpx.AsyncClient):
    owner = await sign_up(client)
    created = await client.put(
        "/api/v1/profiles/me", headers=owner.headers, json=make_profile_body(area_precision="1km")
    )
    viewer, _ = await sign_up_with_profile(client)

    public = await client.get(f"/api/v1/profiles/{created.json()['id']}", headers=viewer.headers)
    feed = await client.get("/api/v1/matches", headers=viewer.headers)

    assert "area_precision" not in public.text
    assert "area_precision" not in feed.text
