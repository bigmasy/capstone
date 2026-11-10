"""Password reset over HTTP: the link, the new password, and what the answers never reveal."""

import asyncio
import logging

import httpx
import pytest

from tests.integration.helpers import PASSWORD, confirmation_token, sign_up

API = "/api/v1"
NEW_PASSWORD = "a brand new passphrase"


def outbox(client: httpx.AsyncClient):
    return client._transport.app.state.mailer.sent  # type: ignore[attr-defined]  # noqa: SLF001


async def forgot(client: httpx.AsyncClient, email: str) -> httpx.Response:
    return await client.post(f"{API}/auth/forgot-password", json={"email": email})


async def reset(client: httpx.AsyncClient, token: str, password: str) -> httpx.Response:
    return await client.post(
        f"{API}/auth/reset-password", json={"token": token, "password": password}
    )


async def login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post(f"{API}/auth/login", json={"email": email, "password": password})


async def test_forgetting_the_password_and_setting_a_new_one(client: httpx.AsyncClient):
    actor = await sign_up(client)

    assert (await forgot(client, actor.email)).status_code == 204
    token = confirmation_token(client, actor.email)
    done = await reset(client, token, NEW_PASSWORD)

    assert done.status_code == 204
    assert (await login(client, actor.email, NEW_PASSWORD)).status_code == 200
    assert (await login(client, actor.email, PASSWORD)).status_code == 401


async def test_known_and_unknown_addresses_get_the_same_answer(client: httpx.AsyncClient):
    actor = await sign_up(client)
    before = len(outbox(client))

    known = await forgot(client, actor.email)
    unknown = await forgot(client, "nobody-here@example.org")

    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""
    sent = outbox(client)[before:]
    assert [m.to for m in sent] == [actor.email]


async def test_a_second_request_inside_the_cooldown_sends_nothing(client: httpx.AsyncClient):
    actor = await sign_up(client)
    before = len(outbox(client))

    first = await forgot(client, actor.email)
    second = await forgot(client, actor.email)

    assert first.status_code == second.status_code == 204
    assert len(outbox(client)) - before == 1


async def test_the_address_is_matched_ignoring_case_and_spaces(client: httpx.AsyncClient):
    actor = await sign_up(client)
    before = len(outbox(client))

    await forgot(client, f"  {actor.email.upper()} ")

    assert [m.to for m in outbox(client)[before:]] == [actor.email]


async def test_the_link_works_once_and_a_wrong_token_is_a_plain_400(client: httpx.AsyncClient):
    actor = await sign_up(client)
    await forgot(client, actor.email)
    token = confirmation_token(client, actor.email)

    first = await reset(client, token, NEW_PASSWORD)
    second = await reset(client, token, "yet another passphrase")
    unknown = await reset(client, "x" * 43, NEW_PASSWORD)

    assert first.status_code == 204
    assert second.status_code == unknown.status_code == 400
    assert second.json() == unknown.json()
    assert token not in second.text
    # The second attempt did not change anything
    assert (await login(client, actor.email, NEW_PASSWORD)).status_code == 200


async def test_a_weak_password_is_refused_and_the_link_stays_usable(client: httpx.AsyncClient):
    actor = await sign_up(client)
    await forgot(client, actor.email)
    token = confirmation_token(client, actor.email)

    weak = await reset(client, token, "tiny-pw")

    assert weak.status_code == 422
    assert "tiny-pw" not in weak.text
    assert (await reset(client, token, NEW_PASSWORD)).status_code == 204


@pytest.mark.parametrize("token", ["", "abcdef", "has spaces " * 4, "z" * 500, "bad/chars/" * 5])
async def test_a_malformed_token_is_rejected_before_any_lookup(
    client: httpx.AsyncClient, token: str
):
    response = await reset(client, token, NEW_PASSWORD)

    assert response.status_code == 422
    assert NEW_PASSWORD not in response.text


@pytest.mark.parametrize("body", [{}, {"email": ""}, {"email": "no-at-sign"}, {"email": "a@b"}])
async def test_a_malformed_address_is_a_validation_error(client: httpx.AsyncClient, body: dict):
    assert (await client.post(f"{API}/auth/forgot-password", json=body)).status_code == 422


async def test_extra_fields_are_refused(client: httpx.AsyncClient):
    response = await client.post(
        f"{API}/auth/forgot-password", json={"email": "a@example.org", "admin": True}
    )

    assert response.status_code == 422


async def test_a_session_from_before_the_reset_stops_working(client: httpx.AsyncClient):
    actor = await sign_up(client)
    assert (await client.get(f"{API}/auth/me", headers=actor.headers)).status_code == 200
    # Tokens carry whole seconds; wait so that the old one is strictly older than the reset
    await asyncio.sleep(1.2)

    await forgot(client, actor.email)
    await reset(client, confirmation_token(client, actor.email), NEW_PASSWORD)

    assert (await client.get(f"{API}/auth/me", headers=actor.headers)).status_code == 401
    fresh = await login(client, actor.email, NEW_PASSWORD)
    me = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}
    )
    assert me.status_code == 200


async def test_the_link_also_confirms_an_unconfirmed_account(client: httpx.AsyncClient):
    actor = await sign_up(client, confirmed=False)
    assert (await client.get(f"{API}/auth/me", headers=actor.headers)).json()[
        "email_verified"
    ] is False

    await forgot(client, actor.email)
    await reset(client, confirmation_token(client, actor.email), NEW_PASSWORD)

    fresh = await login(client, actor.email, NEW_PASSWORD)
    me = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}
    )
    assert me.json()["email_verified"] is True


async def test_neither_the_address_nor_the_password_reaches_the_log(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
):
    actor = await sign_up(client)
    with caplog.at_level(logging.DEBUG):
        await forgot(client, actor.email)
        token = confirmation_token(client, actor.email)
        await reset(client, token, NEW_PASSWORD)

    assert actor.email not in caplog.text
    assert NEW_PASSWORD not in caplog.text
    assert token not in caplog.text


async def test_the_reset_message_names_the_product_and_carries_a_fragment_link(
    client: httpx.AsyncClient,
):
    actor = await sign_up(client)
    await forgot(client, actor.email)

    mail = [m for m in outbox(client) if m.to == actor.email][-1]

    assert mail.subject == "Відновлення пароля на «Поруч»"
    assert "/reset-password#token=" in mail.text
    assert mail.html is not None and "/reset-password#token=" in mail.html
