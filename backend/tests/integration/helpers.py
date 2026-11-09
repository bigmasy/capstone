"""Builders and small helpers shared by the HTTP-level tests."""

from dataclasses import dataclass
from itertools import count
from typing import Any

import httpx

PASSWORD = "correct horse battery"
_numbers = count(1)


@dataclass(frozen=True)
class Actor:
    """A registered user with a token."""

    email: str
    user_id: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        """Authorization header of the actor."""
        return {"Authorization": f"Bearer {self.token}"}


def make_profile_body(**overrides: Any) -> dict[str, Any]:
    """Return a valid ``PUT /profiles/me`` body."""
    body: dict[str, Any] = {
        "display_name": "Orest",
        "district_code": "kyiv_podilskyi",
        "intensity": 3,
        "is_visible": True,
        "latitude": 50.4501,
        "longitude": 30.5234,
        "sports": [{"sport": "swimming", "skill": "intermediate"}],
        "capabilities": [
            {"category": "mobility_lower", "level": 2, "equipment": "wheelchair_active"},
            {"category": "vision", "level": 4},
        ],
        "functional_data_consent": True,
        "contact": "t.me/orest",
    }
    body.update(overrides)
    return body


async def sign_up(client: httpx.AsyncClient, email: str | None = None) -> Actor:
    """Register a user, log in and return the actor."""
    address = email or f"user{next(_numbers)}@example.org"
    registered = await client.post(
        "/api/v1/auth/register", json={"email": address, "password": PASSWORD}
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/v1/auth/login", json={"email": address, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return Actor(email=address, user_id=registered.json()["id"], token=login.json()["access_token"])


async def sign_up_with_profile(
    client: httpx.AsyncClient, **overrides: Any
) -> tuple[Actor, dict[str, Any]]:
    """Register a user, save a profile for them and return both."""
    actor = await sign_up(client)
    response = await client.put(
        "/api/v1/profiles/me", json=make_profile_body(**overrides), headers=actor.headers
    )
    assert response.status_code == 200, response.text
    return actor, response.json()
