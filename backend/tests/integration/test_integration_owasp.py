"""Route x actor matrix for the object routes (OWASP API1 and API2)."""

from uuid import uuid4

import httpx
import pytest

from tests.integration.helpers import PASSWORD, Actor, make_profile_body, sign_up_with_profile

ANONYMOUS = "anonymous"
OTHER = "other"
OWNER = "owner"


@pytest.fixture
async def world(client: httpx.AsyncClient) -> dict[str, object]:
    """A visible and a hidden profile of one owner, plus another user."""
    owner, visible = await sign_up_with_profile(client)
    hidden_owner, hidden = await sign_up_with_profile(client, is_visible=False)
    other, _ = await sign_up_with_profile(client, display_name="Other")
    return {
        "owner": owner,
        "other": other,
        "hidden_owner": hidden_owner,
        "visible_id": visible["id"],
        "hidden_id": hidden["id"],
    }


def headers_for(world: dict[str, object], who: str, owner_key: str = "owner") -> dict[str, str]:
    if who == ANONYMOUS:
        return {}
    actor = world[owner_key if who == OWNER else "other"]
    assert isinstance(actor, Actor)
    return actor.headers


# (case, actor, expected status). Visible profile: any signed-in user sees the public view.
# Hidden profile: nobody, including the owner, gets it through the public route.
PUBLIC_ROUTE_MATRIX = [
    ("visible", ANONYMOUS, 401),
    ("visible", OTHER, 200),
    ("visible", OWNER, 200),
    ("hidden", ANONYMOUS, 401),
    ("hidden", OTHER, 404),
    ("hidden", OWNER, 404),
    ("missing", ANONYMOUS, 401),
    ("missing", OTHER, 404),
    ("missing", OWNER, 404),
]


@pytest.mark.parametrize(("case", "who", "expected"), PUBLIC_ROUTE_MATRIX)
async def test_public_profile_route_matrix(
    client: httpx.AsyncClient, world: dict[str, object], case: str, who: str, expected: int
):
    profile_id = {
        "visible": world["visible_id"],
        "hidden": world["hidden_id"],
        "missing": str(uuid4()),
    }[case]
    owner_key = "hidden_owner" if case == "hidden" else "owner"

    response = await client.get(
        f"/api/v1/profiles/{profile_id}", headers=headers_for(world, who, owner_key)
    )

    assert response.status_code == expected


OWN_ROUTES = [
    ("GET", "/api/v1/profiles/me"),
    ("PUT", "/api/v1/profiles/me"),
    ("DELETE", "/api/v1/profiles/me"),
    ("GET", "/api/v1/auth/me"),
    ("DELETE", "/api/v1/auth/me"),
]


@pytest.mark.parametrize(("method", "path"), OWN_ROUTES)
async def test_own_routes_require_authentication(
    client: httpx.AsyncClient, world: dict[str, object], method: str, path: str
):
    response = await client.request(method, path, json=make_profile_body())

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_there_is_no_route_to_reach_another_users_private_data(
    client: httpx.AsyncClient, world: dict[str, object]
):
    # The only parameterised route is the public view; ids of other users are not accepted
    # anywhere else, so "me" routes always act on the token's subject.
    owner = world["owner"]
    other = world["other"]
    assert isinstance(owner, Actor) and isinstance(other, Actor)
    before = (await client.get("/api/v1/profiles/me", headers=owner.headers)).json()

    await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(display_name="Hijacked", is_visible=False),
        headers=other.headers,
    )
    await client.delete("/api/v1/profiles/me", headers=other.headers)
    await client.delete("/api/v1/auth/me", headers=other.headers)

    after = (await client.get("/api/v1/profiles/me", headers=owner.headers)).json()
    assert after == before


async def test_identifiers_in_the_body_cannot_redirect_a_write(
    client: httpx.AsyncClient, world: dict[str, object]
):
    other = world["other"]
    assert isinstance(other, Actor)

    response = await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(user_id=world["visible_id"], id=world["visible_id"]),
        headers=other.headers,
    )

    assert response.status_code == 422


async def test_oversized_inputs_are_rejected(client: httpx.AsyncClient, world: dict[str, object]):
    other = world["other"]
    assert isinstance(other, Actor)
    huge = [
        make_profile_body(display_name="x" * 10_000),
        make_profile_body(contact="x" * 10_000),
        make_profile_body(
            capabilities=[{"category": "vision", "level": 1}] * 50,
        ),
    ]

    for body in huge:
        response = await client.put("/api/v1/profiles/me", json=body, headers=other.headers)
        assert response.status_code == 422

    long_password = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.org", "password": PASSWORD * 100}
    )
    assert long_password.status_code == 422
