from typing import Annotated
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.handlers import known_loc_names, safe_error, safe_loc
from app.domain.account import (
    LOCATION_INCOMPLETE_MESSAGE,
    LOCATION_REQUIRED_MESSAGE,
    LocationRequiredError,
)
from app.domain.errors import (
    AccessDeniedError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from app.domain.invitations import CONTACT_REQUIRED_MESSAGE, ContactRequiredError

CANARY = "canary-51.5007-31.2993"


class Place(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float
    longitude: float


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=10)
    place: Place
    tags: list[str] = []


@pytest.fixture
def probe_app(app: FastAPI) -> FastAPI:
    @app.post("/probe", response_model=None)
    async def probe(payload: Payload, limit: Annotated[int, Query(ge=1, le=5)] = 1) -> None:
        return None

    @app.get("/raise/{kind}", response_model=None)
    async def raise_error(kind: str) -> None:
        errors = {
            "auth": AuthenticationError("bad credentials"),
            "denied": AccessDeniedError("not allowed"),
            "missing": NotFoundError("no such thing"),
            "conflict": ConflictError("already done"),
        }
        raise errors[kind]

    return app


@pytest.mark.parametrize(
    ("kind", "code", "message"),
    [
        ("auth", 401, "bad credentials"),
        ("denied", 403, "not allowed"),
        ("missing", 404, "no such thing"),
        ("conflict", 409, "already done"),
    ],
)
async def test_domain_errors_map_to_http_status(
    probe_app: FastAPI, client: httpx.AsyncClient, kind: str, code: int, message: str
):
    response = await client.get(f"/raise/{kind}")

    assert response.status_code == code
    assert response.json() == {"detail": message}


async def test_authentication_error_advertises_bearer(
    probe_app: FastAPI, client: httpx.AsyncClient
):
    response = await client.get("/raise/auth")

    assert response.headers["www-authenticate"] == "Bearer"


async def test_validation_error_has_only_type_loc_msg(
    probe_app: FastAPI, client: httpx.AsyncClient
):
    body = {"name": "x" * 50, "place": {"latitude": CANARY, "longitude": 1.0}}

    response = await client.post("/probe", json=body)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert len(errors) == 2
    for error in errors:
        assert set(error) == {"type", "loc", "msg"}
    assert CANARY not in response.text
    assert "xxxxxxxxxx" not in response.text


async def test_known_location_names_are_kept(probe_app: FastAPI, client: httpx.AsyncClient):
    body = {"name": "x" * 50, "place": {"latitude": 1.0, "longitude": 1.0}}

    response = await client.post("/probe", json=body)

    assert response.json()["detail"][0]["loc"] == ["body", "name"]


async def test_nested_model_names_come_from_registered_models(
    probe_app: FastAPI, client: httpx.AsyncClient
):
    body = {"name": "ok", "place": {"latitude": "bad", "longitude": 1.0}}

    response = await client.post("/probe", json=body)

    assert response.json()["detail"][0]["loc"] == ["body", "place", "latitude"]


async def test_unknown_keys_are_masked(probe_app: FastAPI, client: httpx.AsyncClient):
    body = {
        "name": "ok",
        "place": {"latitude": 1.0, "longitude": 1.0, CANARY: 1},
        f"top-{CANARY}": 2,
    }

    response = await client.post("/probe", json=body)

    assert response.status_code == 422
    assert CANARY not in response.text
    locs = [error["loc"] for error in response.json()["detail"]]
    assert ["body", "place", "?"] in locs
    assert ["body", "?"] in locs


async def test_query_parameters_are_validated_without_echo(
    probe_app: FastAPI, client: httpx.AsyncClient
):
    response = await client.post(
        "/probe?limit=99",
        json={"name": "ok", "place": {"latitude": 1.0, "longitude": 1.0}},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "limit"]
    assert "99" not in response.text


async def test_list_indexes_are_kept(probe_app: FastAPI, client: httpx.AsyncClient):
    body = {"name": "ok", "place": {"latitude": 1.0, "longitude": 1.0}, "tags": ["a", 3]}

    response = await client.post("/probe", json=body)

    assert response.json()["detail"][0]["loc"] == ["body", "tags", 1]


def test_known_names_follow_the_registered_routes(probe_app: FastAPI):
    names = known_loc_names(probe_app)

    assert {"body", "query", "name", "place", "latitude", "longitude", "tags", "limit"} <= names
    assert CANARY not in names


def test_safe_loc_masks_unknown_strings_only():
    assert safe_loc(["body", "evil", 2, "name"], frozenset({"body", "name"})) == [
        "body",
        "?",
        2,
        "name",
    ]


def test_safe_error_uses_a_fixed_message_and_masks_the_location():
    error = safe_error("string_too_long", ["body", "evil", "name"], frozenset({"body", "name"}))

    assert error == {
        "type": "string_too_long",
        "loc": ["body", "?", "name"],
        "msg": "Text is too long",
    }


def test_safe_error_reports_unknown_types_generically():
    error = safe_error(f"custom-{CANARY}", ["body"], frozenset({"body"}))

    assert error == {"type": "invalid", "loc": ["body"], "msg": "Invalid value"}


async def test_messages_that_quote_the_input_are_not_forwarded(
    probe_app: FastAPI, client: httpx.AsyncClient
):
    @probe_app.get("/things/{thing_id}", response_model=None)
    async def thing(thing_id: UUID) -> None:
        return None

    responses = [
        await client.get(f"/things/{CANARY}"),
        await client.post(
            "/probe",
            content=f'{{"name": "{CANARY}", ',
            headers={"content-type": "application/json"},
        ),
        await client.post(
            "/probe", json={"name": CANARY, "place": {"latitude": CANARY, "longitude": 1.0}}
        ),
    ]

    for response in responses:
        assert response.status_code == 422
        assert CANARY not in response.text
        assert "input" not in response.text
        assert "ctx" not in response.text
        assert "url" not in response.text
        for error in response.json()["detail"]:
            assert set(error) == {"type", "loc", "msg"}


async def test_location_required_is_a_422_in_the_validation_shape(
    app: FastAPI, client: httpx.AsyncClient
):
    @app.get("/raise-location", response_model=None)
    async def raise_location() -> None:
        raise LocationRequiredError

    response = await client.get("/raise-location")

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {"type": "location_required", "loc": ["body", name], "msg": LOCATION_REQUIRED_MESSAGE}
            for name in ("latitude", "longitude")
        ]
    }


async def test_contact_required_is_a_409_with_a_stable_code(
    app: FastAPI, client: httpx.AsyncClient
):
    @app.get("/raise-contact", response_model=None)
    async def raise_contact() -> None:
        raise ContactRequiredError

    response = await client.get("/raise-contact")

    assert response.status_code == 409
    assert response.json() == {"detail": CONTACT_REQUIRED_MESSAGE, "code": "contact_required"}


def test_the_incomplete_location_type_has_a_fixed_message():
    error = safe_error("location_incomplete", ["body"], frozenset({"body"}))

    assert error == {
        "type": "location_incomplete",
        "loc": ["body"],
        "msg": LOCATION_INCOMPLETE_MESSAGE,
    }
