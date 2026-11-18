import re
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.database.models import FunctionalCapability, Profile
from app.domain.privacy import coarsen
from tests.integration.helpers import make_profile_body, sign_up, sign_up_with_profile

OWNER_FIELDS = {
    "id", "display_name", "district_code", "intensity", "sports", "is_visible",
    "functional_data_consent", "functional_consent_at", "capabilities", "contact",
    "created_at", "updated_at", "has_photo", "area_precision",
}  # fmt: skip


def all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in all_keys(item)}
    return set()


async def test_put_creates_the_profile_and_returns_the_owner_view(client: httpx.AsyncClient):
    actor = await sign_up(client)

    response = await client.put(
        "/api/v1/profiles/me", json=make_profile_body(), headers=actor.headers
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == OWNER_FIELDS
    assert body["display_name"] == "Orest"
    assert body["sports"] == [{"sport": "swimming", "skill": "intermediate"}]
    assert {c["category"] for c in body["capabilities"]} == {"mobility_lower", "vision"}
    assert body["functional_data_consent"] is True
    assert body["contact"] == "t.me/orest"


async def test_all_json_keys_are_snake_case_and_location_free(client: httpx.AsyncClient):
    actor, profile = await sign_up_with_profile(client)
    me = (await client.get("/api/v1/profiles/me", headers=actor.headers)).json()

    for payload in (profile, me):
        keys = all_keys(payload)
        assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", key) for key in keys), keys
        assert not {"latitude", "longitude", "area_lat", "area_lon", "cell"} & keys


async def test_stored_location_is_the_cell_centre_never_the_input(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    lat, lon = 50.451234567, 30.523456789
    await sign_up_with_profile(client, latitude=lat, longitude=lon)

    async with async_sessionmaker(engine)() as session:
        row = (await session.execute(select(Profile))).scalar_one()

    cell = coarsen(lat, lon)
    assert (row.area_lat, row.area_lon) == (cell.latitude, cell.longitude)
    assert (row.area_lat, row.area_lon) != (lat, lon)


async def test_two_nearby_points_store_the_same_cell(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    await sign_up_with_profile(client, latitude=50.4501, longitude=30.5234)
    await sign_up_with_profile(client, latitude=50.4510, longitude=30.5240)

    async with async_sessionmaker(engine)() as session:
        rows = (await session.execute(select(Profile.area_lat, Profile.area_lon))).all()

    assert len(set(rows)) == 1


async def test_without_consent_capabilities_are_not_stored(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, profile = await sign_up_with_profile(client, functional_data_consent=False)

    assert profile["capabilities"] == []
    assert profile["functional_data_consent"] is False
    assert profile["functional_consent_at"] is None
    async with async_sessionmaker(engine)() as session:
        assert await session.scalar(select(func.count()).select_from(FunctionalCapability)) == 0


async def test_withdrawing_consent_deletes_capabilities_and_the_timestamp(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, first = await sign_up_with_profile(client)
    assert first["functional_consent_at"] is not None

    response = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(functional_data_consent=False),
        headers=actor.headers,
    )

    assert response.json()["capabilities"] == []
    assert response.json()["functional_consent_at"] is None
    async with async_sessionmaker(engine)() as session:
        assert await session.scalar(select(func.count()).select_from(FunctionalCapability)) == 0


async def test_consent_time_is_kept_when_the_profile_is_saved_again(client: httpx.AsyncClient):
    actor, first = await sign_up_with_profile(client)

    second = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(display_name="Renamed"),
        headers=actor.headers,
    )

    assert second.json()["display_name"] == "Renamed"
    assert second.json()["functional_consent_at"] == first["functional_consent_at"]
    assert second.json()["id"] == first["id"]


async def test_put_replaces_sports_and_capabilities(client: httpx.AsyncClient):
    actor, _ = await sign_up_with_profile(client)

    response = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(
            sports=[{"sport": "archery", "skill": "advanced"}, {"sport": "rowing"}],
            capabilities=[{"category": "hearing", "level": 3, "equipment": "hearing_aid"}],
        ),
        headers=actor.headers,
    )

    body = response.json()
    assert [s["sport"] for s in body["sports"]] == ["archery", "rowing"]
    assert body["sports"][1]["skill"] == "beginner"
    assert [c["category"] for c in body["capabilities"]] == ["hearing"]


async def test_get_my_profile_before_and_after_creation(client: httpx.AsyncClient):
    actor = await sign_up(client)

    assert (await client.get("/api/v1/profiles/me", headers=actor.headers)).status_code == 404

    await client.put("/api/v1/profiles/me", json=make_profile_body(), headers=actor.headers)
    response = await client.get("/api/v1/profiles/me", headers=actor.headers)

    assert response.status_code == 200
    assert set(response.json()) == OWNER_FIELDS


async def test_delete_my_profile_keeps_the_account(client: httpx.AsyncClient):
    actor, _ = await sign_up_with_profile(client)

    assert (await client.delete("/api/v1/profiles/me", headers=actor.headers)).status_code == 204
    assert (await client.get("/api/v1/profiles/me", headers=actor.headers)).status_code == 404
    assert (await client.delete("/api/v1/profiles/me", headers=actor.headers)).status_code == 404
    assert (await client.get("/api/v1/auth/me", headers=actor.headers)).status_code == 200


async def test_public_view_has_no_private_fields(client: httpx.AsyncClient):
    owner, profile = await sign_up_with_profile(client)
    viewer = await sign_up(client)

    response = await client.get(f"/api/v1/profiles/{profile['id']}", headers=viewer.headers)

    assert response.status_code == 200
    assert set(response.json()) == {
        "id", "display_name", "district_code", "intensity", "sports", "has_photo",
    }  # fmt: skip


async def test_hidden_and_missing_profiles_give_the_same_404(client: httpx.AsyncClient):
    _, hidden = await sign_up_with_profile(client, is_visible=False)
    viewer = await sign_up(client)

    hidden_response = await client.get(f"/api/v1/profiles/{hidden['id']}", headers=viewer.headers)
    missing_response = await client.get(f"/api/v1/profiles/{uuid4()}", headers=viewer.headers)

    assert hidden_response.status_code == missing_response.status_code == 404
    assert hidden_response.json() == missing_response.json()


async def test_invalid_profile_bodies_are_rejected(client: httpx.AsyncClient):
    actor = await sign_up(client)
    bad_bodies = [
        make_profile_body(intensity=9),
        make_profile_body(latitude=123.0),
        make_profile_body(sports=[]),
        make_profile_body(sports=[{"sport": "swimming"}, {"sport": "swimming"}]),
        make_profile_body(
            capabilities=[{"category": "vision", "level": 2, "equipment": "handcycle"}]
        ),
        make_profile_body(display_name="x" * 61),
    ]

    for body in bad_bodies:
        response = await client.put("/api/v1/profiles/me", json=body, headers=actor.headers)
        assert response.status_code == 422
        assert all(set(e) == {"type", "loc", "msg"} for e in response.json()["detail"])


async def test_invalid_profile_id_is_a_validation_error(client: httpx.AsyncClient):
    actor = await sign_up(client)

    response = await client.get("/api/v1/profiles/not-a-uuid", headers=actor.headers)

    assert response.status_code == 422
    assert "not-a-uuid" not in response.text


async def test_taxonomy_is_public_and_holds_codes_only(client: httpx.AsyncClient):
    response = await client.get("/api/v1/taxonomy")

    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert "swimming" in body["sports"]
    assert all(isinstance(code, str) for code in body["sports"])
    assert {"name", "label", "description"}.isdisjoint(all_keys(body))
    equipment = {item["code"]: item["categories"] for item in body["equipment"]}
    assert equipment["hearing_aid"] == ["hearing"]
    assert body["capability_levels"] == [0, 1, 2, 3, 4]


async def stored_cell(engine: AsyncEngine) -> tuple[float, float]:
    async with async_sessionmaker(engine)() as session:
        row = (await session.execute(select(Profile))).scalar_one()
    return row.area_lat, row.area_lon


def without_location(**overrides: Any) -> dict[str, Any]:
    body = make_profile_body(**overrides)
    del body["latitude"], body["longitude"]
    return body


async def test_an_update_without_location_keeps_the_stored_cell(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, _ = await sign_up_with_profile(client, latitude=50.451234, longitude=30.523456)
    cell = coarsen(50.451234, 30.523456)

    response = await client.put(
        "/api/v1/profiles/me",
        json=without_location(contact="t.me/new", display_name="Renamed"),
        headers=actor.headers,
    )

    assert response.status_code == 200
    assert response.json()["contact"] == "t.me/new"
    assert response.json()["display_name"] == "Renamed"
    assert await stored_cell(engine) == (cell.latitude, cell.longitude)


async def test_null_coordinates_also_keep_the_stored_cell(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, _ = await sign_up_with_profile(client)
    before = await stored_cell(engine)

    response = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(latitude=None, longitude=None, contact="t.me/other"),
        headers=actor.headers,
    )

    assert response.status_code == 200
    assert await stored_cell(engine) == before


async def test_an_update_with_a_location_moves_the_cell(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, _ = await sign_up_with_profile(client)

    response = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(latitude=49.8397, longitude=24.0297),
        headers=actor.headers,
    )

    assert response.status_code == 200
    moved = coarsen(49.8397, 24.0297)
    assert await stored_cell(engine) == (moved.latitude, moved.longitude)


async def test_the_first_save_without_location_is_a_422_that_names_the_location_fields(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor = await sign_up(client)

    response = await client.put(
        "/api/v1/profiles/me", json=without_location(), headers=actor.headers
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert {tuple(error["loc"]) for error in errors} == {
        ("body", "latitude"),
        ("body", "longitude"),
    }
    assert all(set(error) == {"type", "loc", "msg"} for error in errors)
    assert len({error["msg"] for error in errors}) == 1
    async with async_sessionmaker(engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Profile)) == 0
    assert (await client.get("/api/v1/profiles/me", headers=actor.headers)).status_code == 404


async def test_one_coordinate_alone_is_a_422_on_create_and_on_update(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, _ = await sign_up_with_profile(client)
    before = await stored_cell(engine)
    newcomer = await sign_up(client)

    for who in (actor, newcomer):
        for field in ("latitude", "longitude"):
            body = without_location()
            body[field] = 12.345
            response = await client.put("/api/v1/profiles/me", json=body, headers=who.headers)
            assert response.status_code == 422
            assert "12.345" not in response.text

    assert await stored_cell(engine) == before


async def test_given_coordinates_keep_their_range_checks_on_update(
    client: httpx.AsyncClient, engine: AsyncEngine
):
    actor, _ = await sign_up_with_profile(client)
    before = await stored_cell(engine)

    for body in (
        make_profile_body(latitude=91.0),
        make_profile_body(longitude=-181.0),
        make_profile_body(latitude="50.4"),
    ):
        response = await client.put("/api/v1/profiles/me", json=body, headers=actor.headers)
        assert response.status_code == 422

    assert await stored_cell(engine) == before


async def test_an_update_without_location_still_applies_the_consent_rule_and_hides_the_location(
    client: httpx.AsyncClient,
):
    actor, _ = await sign_up_with_profile(client)

    response = await client.put(
        "/api/v1/profiles/me",
        json=without_location(functional_data_consent=False),
        headers=actor.headers,
    )

    assert response.json()["capabilities"] == []
    assert not {"latitude", "longitude", "area_lat", "area_lon", "cell"} & all_keys(response.json())
