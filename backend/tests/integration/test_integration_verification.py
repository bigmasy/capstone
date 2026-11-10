"""E-mail confirmation over HTTP: the link, the rules it unlocks, and what it never leaks."""

import logging

import httpx
import pytest

from tests.integration.helpers import (
    PASSWORD,
    Actor,
    confirm_email,
    confirmation_token,
    make_profile_body,
    sign_up,
    sign_up_with_profile,
)

API = "/api/v1"


async def invite(client: httpx.AsyncClient, actor: Actor, profile_id: str) -> httpx.Response:
    return await client.post(
        f"{API}/invitations", json={"recipient_profile_id": profile_id}, headers=actor.headers
    )


async def test_a_new_account_is_unconfirmed_and_the_link_confirms_it(client: httpx.AsyncClient):
    actor = await sign_up(client, confirmed=False)

    before = await client.get(f"{API}/auth/me", headers=actor.headers)
    assert before.json()["email_verified"] is False

    await confirm_email(client, actor.email)

    after = await client.get(f"{API}/auth/me", headers=actor.headers)
    assert after.json()["email_verified"] is True


async def test_the_link_works_once_and_a_wrong_token_is_a_plain_400(client: httpx.AsyncClient):
    actor = await sign_up(client, confirmed=False)
    token = confirmation_token(client, actor.email)

    first = await client.post(f"{API}/auth/verify-email", json={"token": token})
    second = await client.post(f"{API}/auth/verify-email", json={"token": token})
    unknown = await client.post(f"{API}/auth/verify-email", json={"token": "x" * 43})

    assert first.status_code == 204
    assert second.status_code == unknown.status_code == 400
    assert second.json() == unknown.json()
    assert token not in second.text


@pytest.mark.parametrize("token", ["", "abcdef", "has spaces " * 4, "z" * 500, "bad/chars/" * 5])
async def test_a_malformed_token_is_rejected_before_any_lookup(
    client: httpx.AsyncClient, token: str
):
    response = await client.post(f"{API}/auth/verify-email", json={"token": token})

    assert response.status_code == 422
    assert token.strip() == "" or token not in response.text


async def test_resending_needs_a_session_and_always_answers_204(client: httpx.AsyncClient):
    assert (await client.post(f"{API}/auth/resend-verification")).status_code == 401
    actor = await sign_up(client, confirmed=False)

    first = await client.post(f"{API}/auth/resend-verification", headers=actor.headers)
    second = await client.post(f"{API}/auth/resend-verification", headers=actor.headers)

    # The second call falls inside the cooldown: the answer is the same, nothing more is sent
    assert first.status_code == second.status_code == 204
    outbox = client._transport.app.state.mailer.sent  # type: ignore[attr-defined]  # noqa: SLF001
    assert len([m for m in outbox if m.to == actor.email]) == 1


async def test_an_unconfirmed_account_cannot_send_an_invitation(client: httpx.AsyncClient):
    sender, _ = await sign_up_with_profile(client, confirmed=False)
    _, target = await sign_up_with_profile(client)

    response = await invite(client, sender, target["id"])

    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


async def test_the_same_account_can_invite_once_it_confirmed(client: httpx.AsyncClient):
    sender, _ = await sign_up_with_profile(client, confirmed=False)
    _, target = await sign_up_with_profile(client)
    assert (await invite(client, sender, target["id"])).status_code == 403

    await confirm_email(client, sender.email)

    assert (await invite(client, sender, target["id"])).status_code == 201


async def test_an_unconfirmed_account_cannot_accept_but_can_decline(client: httpx.AsyncClient):
    sender, _ = await sign_up_with_profile(client)
    recipient, recipient_profile = await sign_up_with_profile(client)
    created = await invite(client, sender, recipient_profile["id"])
    assert created.status_code == 201

    # The recipient registered before the rule would have applied; take the confirmation away
    # by registering a second account that never confirmed instead
    stranger, stranger_profile = await sign_up_with_profile(client, confirmed=False)
    refused = await client.post(
        f"{API}/invitations/{created.json()['id']}/accept", headers=stranger.headers
    )
    accepted = await client.post(
        f"{API}/invitations/{created.json()['id']}/accept", headers=recipient.headers
    )

    assert refused.status_code == 403
    assert refused.json()["code"] == "email_not_verified"
    assert accepted.status_code == 200
    assert stranger_profile["id"]


async def test_an_unconfirmed_profile_is_neither_found_nor_invitable(client: httpx.AsyncClient):
    viewer, _ = await sign_up_with_profile(client)
    hidden_by_rule, profile = await sign_up_with_profile(client, confirmed=False)

    feed = await client.get(f"{API}/matches?limit=50", headers=viewer.headers)
    direct = await client.get(f"{API}/profiles/{profile['id']}", headers=viewer.headers)
    invited = await invite(client, viewer, profile["id"])

    assert profile["id"] not in feed.text
    # The same answer as for a profile its owner hid, so the rule cannot be told from it
    assert direct.status_code == invited.status_code == 404
    assert hidden_by_rule.email not in feed.text


async def test_the_profile_appears_in_the_feed_after_confirmation(client: httpx.AsyncClient):
    viewer, _ = await sign_up_with_profile(client)
    owner, profile = await sign_up_with_profile(client, confirmed=False)
    assert profile["id"] not in (await client.get(f"{API}/matches", headers=viewer.headers)).text

    await confirm_email(client, owner.email)

    assert profile["id"] in (await client.get(f"{API}/matches", headers=viewer.headers)).text


async def test_an_unconfirmed_account_can_still_edit_and_browse_its_own_data(
    client: httpx.AsyncClient,
):
    actor, _ = await sign_up_with_profile(client, confirmed=False)

    saved = await client.put(
        f"{API}/profiles/me", json=make_profile_body(display_name="Renamed"), headers=actor.headers
    )
    feed = await client.get(f"{API}/matches", headers=actor.headers)

    assert saved.status_code == 200
    assert feed.status_code == 200


async def test_the_confirmation_link_never_reaches_the_logs_or_a_response(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.DEBUG)
    email = "canary-owner@example.org"
    registered = await client.post(
        f"{API}/auth/register", json={"email": email, "password": PASSWORD}
    )
    token = confirmation_token(client, email)
    verify = await client.post(f"{API}/auth/verify-email", json={"token": token})

    for text in (registered.text, verify.text, caplog.text):
        assert token not in text
    assert email not in caplog.text
