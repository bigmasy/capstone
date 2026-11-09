"""Canary scan of the matching feed: private values go in, and must not come out of /matches."""

import json
import logging

import httpx
import pytest

from app.domain.privacy import coarsen
from tests.integration.helpers import Actor, make_profile_body, sign_up
from tests.integration.test_integration_canary import (
    CANARY_CONTACT,
    CANARY_EMAIL,
    CANARY_LAT,
    CANARY_LON,
    coordinate_text_variants,
)

URL = "/api/v1/matches"
VIEWER_LAT, VIEWER_LON = 51.99123456, 31.13987654
VIEWER_EMAIL = "canary-viewer-7732@example.org"
CANARY_NAME = "Canary Owner"
CAPABILITIES = [
    {"category": "hearing", "level": 3, "equipment": "hearing_aid"},
    {"category": "vision", "level": 4},
]


def private_values() -> list[str]:
    """Everything that belongs to the owner or the viewer and is not meant to be returned."""
    viewer_cell = coarsen(VIEWER_LAT, VIEWER_LON)
    return [
        *coordinate_text_variants(),
        str(VIEWER_LAT),
        str(VIEWER_LON),
        "51.99123",
        "31.13987",
        f"{viewer_cell.latitude}",
        f"{viewer_cell.longitude}",
        CANARY_CONTACT,
        CANARY_EMAIL,
        VIEWER_EMAIL,
        "hearing_aid",
        "hearing",
        "vision",
        "equipment",
        "capabilities",
        '"latitude"',
        '"longitude"',
        "distance_km",
        "area_lat",
        "area_lon",
        "argon2",
    ]


async def build_world(client: httpx.AsyncClient) -> tuple[Actor, Actor]:
    owner = await sign_up(client, CANARY_EMAIL)
    viewer = await sign_up(client, VIEWER_EMAIL)
    for actor, name, lat, lon, contact in (
        (owner, CANARY_NAME, CANARY_LAT, CANARY_LON, CANARY_CONTACT),
        (viewer, "Viewer", VIEWER_LAT, VIEWER_LON, None),
    ):
        response = await client.put(
            "/api/v1/profiles/me",
            json=make_profile_body(
                display_name=name,
                latitude=lat,
                longitude=lon,
                contact=contact,
                capabilities=CAPABILITIES,
            ),
            headers=actor.headers,
        )
        assert response.status_code == 200, response.text
    return owner, viewer


def dump(response: httpx.Response) -> str:
    return f"{response.text}\n{json.dumps(dict(response.headers))}"


async def test_no_private_value_of_a_candidate_or_the_viewer_reaches_the_feed(
    client: httpx.AsyncClient,
):
    _, viewer = await build_world(client)

    response = await client.get(URL, headers=viewer.headers)

    assert response.status_code == 200
    [item] = response.json()["items"]
    # The scan is not vacuous: the owner is in the feed, with their public name and a level
    assert item["display_name"] == CANARY_NAME
    assert item["breakdown"]["functional"] == "high"
    haystack = dump(response)
    for canary in private_values():
        assert canary not in haystack, canary


async def test_no_private_value_reaches_the_feed_through_filters_pages_or_errors(
    client: httpx.AsyncClient,
):
    owner, viewer = await build_world(client)
    requests = [
        (viewer, {"radius_km": 5}),
        (viewer, {"skip": 1, "limit": 1}),
        (viewer, {"sport": "swimming"}),
        (viewer, {"limit": 999}),
        (viewer, {"radius_km": "x" * 30 + CANARY_CONTACT}),
        (owner, {}),
    ]

    for actor, params in requests:
        response = await client.get(URL, params=params, headers=actor.headers)
        haystack = dump(response)
        for canary in private_values():
            if actor is owner and canary == CANARY_EMAIL:
                continue
            assert canary not in haystack, (params, canary)
    anonymous = await client.get(URL)
    assert all(canary not in dump(anonymous) for canary in private_values())


async def test_no_private_value_reaches_the_logs_when_the_feed_is_served(
    client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
    capfd: pytest.CaptureFixture[str],
):
    caplog.set_level(logging.DEBUG)
    _, viewer = await build_world(client)

    await client.get(URL, headers=viewer.headers)
    await client.get(URL, params={"radius_km": 10, "sport": "swimming"}, headers=viewer.headers)

    records = " ".join(f"{record.getMessage()} {vars(record)}" for record in caplog.records)
    streams = capfd.readouterr()
    haystack = f"{caplog.text} {records} {streams.out} {streams.err}"
    assert "/api/v1/matches" in haystack  # the access log did run
    for canary in private_values():
        if canary in {"vision", "hearing", "equipment", "capabilities"}:
            # These words also occur in unrelated log lines (profile routes); the values that
            # matter are scanned below
            continue
        assert canary not in haystack, canary
    assert viewer.token not in haystack
