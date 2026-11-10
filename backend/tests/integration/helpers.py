"""Builders and small helpers shared by the HTTP-level tests."""

import re
from dataclasses import dataclass
from itertools import count
from typing import Any

import httpx

from app.core.mail import MemoryMailSender

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


def confirmation_token(client: httpx.AsyncClient, email: str) -> str:
    """Return the token from the latest confirmation message sent to an address.

    :param client: Test client; its application keeps the messages in memory.
    :param email: Address the message was sent to.
    :return: The token in the link.
    """
    # The ASGI transport knows the application it calls, whoever built the client
    app = client._transport.app  # type: ignore[attr-defined]  # noqa: SLF001
    outbox: MemoryMailSender = app.state.mailer
    for mail in reversed(outbox.sent):
        if mail.to == email:
            found = re.search(r"#token=([A-Za-z0-9_-]+)", mail.text)
            assert found, "the message has no link"
            return found.group(1)
    raise AssertionError("no message was sent to the address")


async def confirm_email(client: httpx.AsyncClient, email: str) -> None:
    """Follow the confirmation link of an address, as a person would.

    :param client: Test client.
    :param email: Address of the account.
    """
    done = await client.post(
        "/api/v1/auth/verify-email", json={"token": confirmation_token(client, email)}
    )
    assert done.status_code == 204, done.text


async def sign_up(
    client: httpx.AsyncClient, email: str | None = None, *, confirmed: bool = True
) -> Actor:
    """Register a user, confirm the address, log in and return the actor.

    :param client: Test client.
    :param email: Address; a fresh one when omitted.
    :param confirmed: Follow the confirmation link; pass False for an unconfirmed account.
    :return: The actor.
    """
    address = email or f"user{next(_numbers)}@example.org"
    registered = await client.post(
        "/api/v1/auth/register", json={"email": address, "password": PASSWORD}
    )
    assert registered.status_code == 201, registered.text
    if confirmed:
        await confirm_email(client, address)
    login = await client.post("/api/v1/auth/login", json={"email": address, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return Actor(email=address, user_id=registered.json()["id"], token=login.json()["access_token"])


async def sign_up_with_profile(
    client: httpx.AsyncClient, *, confirmed: bool = True, **overrides: Any
) -> tuple[Actor, dict[str, Any]]:
    """Register a user, save a profile for them and return both."""
    actor = await sign_up(client, confirmed=confirmed)
    response = await client.put(
        "/api/v1/profiles/me", json=make_profile_body(**overrides), headers=actor.headers
    )
    assert response.status_code == 200, response.text
    return actor, response.json()
