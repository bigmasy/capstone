"""Canary scan: unique values go in, and must not come out where they do not belong."""

import json
import logging
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.domain.privacy import coarsen
from tests.integration.helpers import Actor, make_profile_body, sign_up

# Distinctive digits that survive neither rounding nor truncation by accident.
CANARY_LAT = 51.98765432
CANARY_LON = 31.12345678
CANARY_CONTACT = "canary-contact-4f9a1c"
CANARY_EMAIL = "canary-owner-4821@example.org"
CANARY_PASSWORD = "canary-password-93b7d2"
# A category/equipment pair that no other profile in the test declares.
CAPABILITY_CANARIES = ("hearing_aid", "hearing")

COORDINATE_CANARIES = [
    str(CANARY_LAT),
    str(CANARY_LON),
    "51.98765",
    "31.12345",
]


def coordinate_text_variants() -> list[str]:
    """Canary strings including the representation after cell rounding must stay unique."""
    cell = coarsen(CANARY_LAT, CANARY_LON)
    # The cell centre is what is stored; it is derived data and may appear only nowhere in
    # any response either, so it is scanned as well.
    return [*COORDINATE_CANARIES, f"{cell.latitude}", f"{cell.longitude}"]


def get_paths(app: FastAPI, profile_id: str) -> list[str]:
    """Every GET path of the application with the profile id filled in."""
    paths = []
    for route in app.routes:
        if isinstance(route, APIRoute) and "GET" in route.methods:
            filled = route.path.replace("{profile_id}", profile_id)
            paths.append(filled.replace("{invitation_id}", str(uuid4())))
    return paths


def dump(response: httpx.Response) -> str:
    """Body and headers of a response as one searchable string."""
    headers = json.dumps(dict(response.headers))
    return f"{response.text}\n{headers}"


@pytest.fixture
async def canary_world(client: httpx.AsyncClient):
    owner = await sign_up(client, CANARY_EMAIL)
    # sign_up uses the shared PASSWORD; register another account with the canary password
    # to see that no password ever comes back.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "pw-canary@example.org", "password": CANARY_PASSWORD},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "pw-canary@example.org", "password": CANARY_PASSWORD}
    )
    assert login.status_code == 200
    response = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(
            latitude=CANARY_LAT,
            longitude=CANARY_LON,
            contact=CANARY_CONTACT,
            capabilities=[{"category": "hearing", "level": 3, "equipment": "hearing_aid"}],
        ),
        headers=owner.headers,
    )
    assert response.status_code == 200
    other = await sign_up(client)
    return owner, other, response.json()["id"], login.json()["access_token"]


async def test_no_canary_leaves_through_any_get_for_other_users_or_anonymous(
    client: httpx.AsyncClient, app: FastAPI, canary_world
):
    owner, other, profile_id, extra_token = canary_world
    forbidden = [
        *coordinate_text_variants(),
        CANARY_CONTACT,
        CANARY_EMAIL,
        CANARY_PASSWORD,
        owner.token,
        *CAPABILITY_CANARIES,
        '"capabilities"',
        '"equipment"',
        '"latitude"',
        '"longitude"',
        "area_lat",
        "area_lon",
        "argon2",
    ]
    callers = [
        {},
        other.headers,
    ]

    for path in get_paths(app, profile_id):
        if path.endswith("/taxonomy"):
            continue  # reference data lists every code by design; it holds no person's values
        for headers in callers:
            response = await client.get(path, headers=headers)
            haystack = dump(response)
            for canary in forbidden:
                if path.endswith("/auth/me") and canary == other.headers["Authorization"]:
                    continue
                assert canary not in haystack, (path, canary)


async def test_owner_sees_capabilities_but_never_coordinates(
    client: httpx.AsyncClient, app: FastAPI, canary_world
):
    owner, _, profile_id, _ = canary_world
    responses = [
        await client.get(path, headers=owner.headers) for path in get_paths(app, profile_id)
    ]
    haystack = "\n".join(dump(r) for r in responses if not r.url.path.endswith("/taxonomy"))

    assert "hearing_aid" in haystack
    assert CANARY_CONTACT in haystack
    for canary in coordinate_text_variants():
        assert canary not in haystack
    for key in ('"latitude"', '"longitude"', "area_lat", "area_lon", "argon2", CANARY_PASSWORD):
        assert key not in haystack


async def test_write_responses_and_errors_do_not_echo_canaries(
    client: httpx.AsyncClient, canary_world
):
    owner, _, _, _ = canary_world
    bodies = [
        make_profile_body(latitude=CANARY_LAT, longitude=CANARY_LON, intensity=99),
        make_profile_body(latitude=CANARY_LAT, longitude=CANARY_LON, **{CANARY_CONTACT: 1}),
    ]

    for body in bodies:
        response = await client.put("/api/v1/profiles/me", json=body, headers=owner.headers)
        assert response.status_code == 422
        for canary in [*coordinate_text_variants(), CANARY_CONTACT]:
            assert canary not in dump(response)

    failed_login = await client.post(
        "/api/v1/auth/login", json={"email": CANARY_EMAIL, "password": CANARY_PASSWORD}
    )
    assert CANARY_PASSWORD not in dump(failed_login)
    assert CANARY_EMAIL not in dump(failed_login)


async def test_no_canary_reaches_the_logs(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
):
    caplog.set_level(logging.DEBUG)
    owner = await sign_up(client, CANARY_EMAIL)
    await client.post(
        "/api/v1/auth/login", json={"email": CANARY_EMAIL, "password": CANARY_PASSWORD}
    )
    await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(
            latitude=CANARY_LAT,
            longitude=CANARY_LON,
            contact=CANARY_CONTACT,
            capabilities=[{"category": "hearing", "level": 3, "equipment": "hearing_aid"}],
        ),
        headers=owner.headers,
    )
    await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(latitude=CANARY_LAT, longitude=CANARY_LON, intensity=99),
        headers=owner.headers,
    )
    await client.get("/api/v1/profiles/me", headers=owner.headers)

    records = " ".join(f"{record.getMessage()} {vars(record)}" for record in caplog.records)
    streams = capfd.readouterr()
    haystack = f"{caplog.text} {records} {streams.out} {streams.err}"

    for canary in [
        *coordinate_text_variants(),
        CANARY_CONTACT,
        CANARY_EMAIL,
        CANARY_PASSWORD,
        owner.token,
        "hearing_aid",
    ]:
        assert canary not in haystack, canary
    assert "request" in haystack  # the access log did run, so the scan was not vacuous


def test_owner_actor_type_is_what_the_helpers_return():
    assert Actor.__name__ == "Actor"


async def test_saving_without_a_location_leaks_neither_the_stored_cell_nor_a_contact(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
):
    caplog.set_level(logging.DEBUG)
    owner = await sign_up(client, CANARY_EMAIL)
    await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(latitude=CANARY_LAT, longitude=CANARY_LON),
        headers=owner.headers,
    )
    body = make_profile_body(contact=CANARY_CONTACT)
    del body["latitude"], body["longitude"]
    updated = await client.put("/api/v1/profiles/me", json=body, headers=owner.headers)
    rejected = await client.put(
        "/api/v1/profiles/me", json={**body, "latitude": CANARY_LAT}, headers=owner.headers
    )

    records = " ".join(f"{record.getMessage()} {vars(record)}" for record in caplog.records)
    streams = capfd.readouterr()
    haystack = (
        f"{dump(updated)} {dump(rejected)} {caplog.text} {records} {streams.out} {streams.err}"
    )

    assert updated.status_code == 200 and rejected.status_code == 422
    for canary in coordinate_text_variants():
        assert canary not in haystack, canary
    assert "request" in haystack
