"""HTTP flows of the invitation routes: lifecycle, role and state errors, IDOR, privacy."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import get_invitation_service
from app.composition import build_invitation_service
from app.conf.config import Settings
from app.database.db import DbSession
from app.services.invitations import InvitationService
from tests.integration.helpers import Actor, sign_up, sign_up_with_profile

BASE = "/api/v1/invitations"
T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
SENDER_CONTACT = "canary-sender-contact-7c1e"
RECIPIENT_CONTACT = "canary-recipient-contact-93ab"
OUTSIDER_CONTACT = "canary-outsider-contact-b04d"
MESSAGE = "canary-message-5d2f"
TTL_DAYS = 14


class MutableClock:
    """A clock the test can move."""

    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


@pytest.fixture
def clock(app: FastAPI, settings: Settings) -> MutableClock:
    """Replace the invitation service with one that reads a controllable clock."""
    moving = MutableClock(T0)

    def service_with_clock(db: DbSession) -> InvitationService:
        service = build_invitation_service(db, settings)
        service.clock = moving
        return service

    app.dependency_overrides[get_invitation_service] = service_with_clock
    return moving


@pytest.fixture
async def world(client: httpx.AsyncClient, clock: MutableClock) -> dict[str, Any]:
    """Sender A, recipient B and an unrelated user C with profiles and contacts; N has none."""
    sender, sender_profile = await sign_up_with_profile(
        client, display_name="Sender", contact=SENDER_CONTACT
    )
    recipient, recipient_profile = await sign_up_with_profile(
        client, display_name="Recipient", contact=RECIPIENT_CONTACT, district_code="kyiv_obolonskyi"
    )
    outsider, outsider_profile = await sign_up_with_profile(
        client, display_name="Outsider", contact=OUTSIDER_CONTACT
    )
    nameless, nameless_profile = await sign_up_with_profile(
        client, display_name="No contact", contact=None
    )
    return {
        "a": sender,
        "b": recipient,
        "c": outsider,
        "n": nameless,
        "a_profile": sender_profile["id"],
        "b_profile": recipient_profile["id"],
        "c_profile": outsider_profile["id"],
        "n_profile": nameless_profile["id"],
    }


async def invite(
    client: httpx.AsyncClient, actor: Actor, profile_id: str, **body: Any
) -> httpx.Response:
    return await client.post(
        BASE, json={"recipient_profile_id": profile_id, **body}, headers=actor.headers
    )


async def act(client: httpx.AsyncClient, actor: Actor, invitation_id: str, action: str):
    return await client.post(f"{BASE}/{invitation_id}/{action}", headers=actor.headers)


async def send(client: httpx.AsyncClient, world: dict[str, Any], **body: Any) -> dict[str, Any]:
    response = await invite(client, world["a"], world["b_profile"], **body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_sending_returns_the_outgoing_form_with_the_recipient_public_profile(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    response = await invite(client, world["a"], world["b_profile"])

    assert response.status_code == 201
    body = response.json()
    assert body["direction"] == "outgoing"
    assert body["status"] == "pending"
    assert "message" not in body
    assert body["responded_at"] is None
    created = datetime.fromisoformat(body["created_at"])
    assert datetime.fromisoformat(body["expires_at"]) == created + timedelta(days=TTL_DAYS)
    assert body["recipient"]["display_name"] == "Recipient"
    assert body["recipient"]["district_code"] == "kyiv_obolonskyi"
    assert body["recipient"]["contact"] is None
    assert "sender" not in body


async def test_the_recipient_sees_the_incoming_form_with_the_sender(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)

    response = await client.get(f"{BASE}/{sent['id']}", headers=world["b"].headers)

    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "incoming"
    assert "message" not in body
    assert body["sender"]["display_name"] == "Sender"
    assert body["sender"]["contact"] is None
    assert "recipient" not in body


async def test_accepting_releases_each_contact_to_the_other_party_only(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)

    accepted = await act(client, world["b"], sent["id"], "accept")
    as_sender = await client.get(f"{BASE}/{sent['id']}", headers=world["a"].headers)
    as_outsider = await client.get(f"{BASE}/{sent['id']}", headers=world["c"].headers)

    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["responded_at"] is not None
    assert accepted.json()["sender"]["contact"] == SENDER_CONTACT
    assert as_sender.json()["recipient"]["contact"] == RECIPIENT_CONTACT
    assert as_outsider.status_code == 404
    assert SENDER_CONTACT not in as_outsider.text and RECIPIENT_CONTACT not in as_outsider.text


async def test_an_accepted_invitation_carries_the_contact_of_both_parties(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await invite(client, world["c"], world["b_profile"])
    accepted = await act(client, world["b"], sent.json()["id"], "accept")

    as_sender = await client.get(f"{BASE}/{sent.json()['id']}", headers=world["c"].headers)
    listed = await client.get(BASE, params={"status": "accepted"}, headers=world["b"].headers)

    assert accepted.json()["sender"]["contact"] == OUTSIDER_CONTACT
    assert as_sender.json()["recipient"]["contact"] == RECIPIENT_CONTACT
    assert listed.json()[0]["sender"]["contact"] == OUTSIDER_CONTACT


async def test_sending_without_a_contact_is_a_coded_conflict_and_creates_nothing(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    response = await invite(client, world["n"], world["b_profile"])

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Add a contact to your profile to send and accept invitations",
        "code": "contact_required",
    }
    listing = await client.get(BASE, headers=world["b"].headers)
    assert listing.json() == []


async def test_the_contact_rule_does_not_tell_a_hidden_profile_from_a_missing_one(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    _, hidden_profile = await sign_up_with_profile(client, is_visible=False)

    # A sender without a contact is stopped by the contact rule whatever the target is
    for target in (hidden_profile["id"], str(uuid4())):
        response = await invite(client, world["n"], target)
        assert response.status_code == 409
        assert response.json()["code"] == "contact_required"
    # A sender with a contact still gets the identical 404 for both
    answers = [
        await invite(client, world["a"], target) for target in (hidden_profile["id"], str(uuid4()))
    ]
    assert [a.status_code for a in answers] == [404, 404]
    assert answers[0].json() == answers[1].json()


async def test_accepting_without_a_contact_is_a_coded_conflict_that_keeps_it_pending(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await invite(client, world["a"], world["n_profile"])
    assert sent.status_code == 201

    refused = await act(client, world["n"], sent.json()["id"], "accept")
    after = await client.get(f"{BASE}/{sent.json()['id']}", headers=world["a"].headers)

    assert refused.status_code == 409
    assert refused.json() == {
        "detail": "Add a contact to your profile to send and accept invitations",
        "code": "contact_required",
    }
    assert after.json()["status"] == "pending"
    assert after.json()["recipient"]["contact"] is None
    assert SENDER_CONTACT not in refused.text


async def test_accepting_works_once_the_contact_is_added(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await invite(client, world["a"], world["n_profile"])
    refused = await act(client, world["n"], sent.json()["id"], "accept")

    saved = await client.put(
        "/api/v1/profiles/me",
        json={**(await _own_profile_body(client, world["n"])), "contact": "t.me/nameless"},
        headers=world["n"].headers,
    )
    accepted = await act(client, world["n"], sent.json()["id"], "accept")

    assert refused.status_code == 409
    assert saved.status_code == 200
    assert accepted.status_code == 200
    assert accepted.json()["sender"]["contact"] == SENDER_CONTACT
    as_sender = await client.get(f"{BASE}/{sent.json()['id']}", headers=world["a"].headers)
    assert as_sender.json()["recipient"]["contact"] == "t.me/nameless"


async def test_the_accept_checks_keep_their_order_before_the_contact_rule(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await invite(client, world["a"], world["n_profile"])
    invitation_id = sent.json()["id"]

    stranger = await act(client, world["c"], invitation_id, "accept")
    sender_side = await act(client, world["a"], invitation_id, "accept")
    missing = await act(client, world["n"], str(uuid4()), "accept")
    await act(client, world["n"], invitation_id, "decline")
    answered = await act(client, world["n"], invitation_id, "accept")

    assert (stranger.status_code, sender_side.status_code, missing.status_code) == (404, 403, 404)
    assert stranger.json() == missing.json()
    assert answered.status_code == 409
    assert "code" not in answered.json()


async def test_declining_works_without_a_contact(client: httpx.AsyncClient, world: dict[str, Any]):
    sent = await invite(client, world["a"], world["n_profile"])

    declined = await act(client, world["n"], sent.json()["id"], "decline")

    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"


async def _own_profile_body(client: httpx.AsyncClient, actor: Actor) -> dict[str, Any]:
    """Return a ``PUT /profiles/me`` body that repeats the stored profile (location kept)."""
    stored = (await client.get("/api/v1/profiles/me", headers=actor.headers)).json()
    return {
        "display_name": stored["display_name"],
        "district_code": stored["district_code"],
        "intensity": stored["intensity"],
        "is_visible": stored["is_visible"],
        "sports": stored["sports"],
        "capabilities": [],
        "functional_data_consent": False,
    }


async def test_declining_and_cancelling_never_release_a_contact(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    declined_source = await send(client, world)
    declined = await act(client, world["b"], declined_source["id"], "decline")
    cancelled_source = await send(client, world)
    cancelled = await act(client, world["a"], cancelled_source["id"], "cancel")

    assert declined.json()["status"] == "declined"
    assert cancelled.json()["status"] == "cancelled"
    for response in (declined, cancelled):
        assert SENDER_CONTACT not in response.text
        assert RECIPIENT_CONTACT not in response.text
    for actor in (world["a"], world["b"]):
        listing = await client.get(BASE, headers=actor.headers)
        assert SENDER_CONTACT not in listing.text and RECIPIENT_CONTACT not in listing.text


async def test_no_contact_appears_anywhere_before_acceptance(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)
    pages = [
        await client.get(BASE, headers=world["a"].headers),
        await client.get(BASE, headers=world["b"].headers),
        await client.get(BASE, params={"direction": "incoming"}, headers=world["b"].headers),
        await client.get(f"{BASE}/{sent['id']}", headers=world["a"].headers),
        await client.get(f"{BASE}/{sent['id']}", headers=world["b"].headers),
        await client.get(f"/api/v1/profiles/{world['a_profile']}", headers=world["b"].headers),
        await client.get(f"/api/v1/profiles/{world['b_profile']}", headers=world["a"].headers),
    ]

    for page in pages:
        assert page.status_code == 200
        assert SENDER_CONTACT not in page.text and RECIPIENT_CONTACT not in page.text


async def test_the_other_party_never_shows_location_or_functional_data(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)
    await act(client, world["b"], sent["id"], "accept")

    for actor in (world["a"], world["b"]):
        text = (await client.get(f"{BASE}/{sent['id']}", headers=actor.headers)).text

        for forbidden in (
            "latitude",
            "longitude",
            "area_",
            "capabilit",
            "equipment",
            "email",
            "hearing",
            "mobility",
        ):
            assert forbidden not in text.lower()


async def test_every_route_requires_authentication(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)
    calls: list[Callable[[], Any]] = [
        lambda: client.post(BASE, json={"recipient_profile_id": world["b_profile"]}),
        lambda: client.get(BASE),
        lambda: client.get(f"{BASE}/{sent['id']}"),
        lambda: client.post(f"{BASE}/{sent['id']}/accept"),
        lambda: client.post(f"{BASE}/{sent['id']}/decline"),
        lambda: client.post(f"{BASE}/{sent['id']}/cancel"),
    ]

    for call in calls:
        response = await call()
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


async def test_a_user_who_is_not_a_participant_cannot_see_or_act(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)
    outsider = world["c"]

    read = await client.get(f"{BASE}/{sent['id']}", headers=outsider.headers)
    actions = [await act(client, outsider, sent["id"], a) for a in ("accept", "decline", "cancel")]
    listing = await client.get(BASE, headers=outsider.headers)
    missing = await client.get(f"{BASE}/{uuid4()}", headers=outsider.headers)

    assert read.status_code == 404
    assert [r.status_code for r in actions] == [404, 404, 404]
    assert read.json() == missing.json()
    assert listing.json() == []
    # The invitation is untouched
    again = await client.get(f"{BASE}/{sent['id']}", headers=world["a"].headers)
    assert again.json()["status"] == "pending"


@pytest.mark.parametrize(("actor", "action"), [("a", "accept"), ("a", "decline"), ("b", "cancel")])
async def test_the_wrong_role_gets_403(
    client: httpx.AsyncClient, world: dict[str, Any], actor: str, action: str
):
    sent = await send(client, world)

    response = await act(client, world[actor], sent["id"], action)

    assert response.status_code == 403


async def test_the_role_is_checked_before_the_state(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)
    await act(client, world["a"], sent["id"], "cancel")

    # 403, not 409: the sender may never accept and learns nothing about the state
    response = await act(client, world["a"], sent["id"], "accept")

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("accept", "accept"),
        ("accept", "decline"),
        ("decline", "accept"),
    ],
)
async def test_answering_twice_is_a_conflict(
    client: httpx.AsyncClient, world: dict[str, Any], first: str, second: str
):
    sent = await send(client, world)
    await act(client, world["b"], sent["id"], first)

    response = await act(client, world["b"], sent["id"], second)

    assert response.status_code == 409


async def test_cancelling_an_accepted_invitation_is_a_conflict(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)
    await act(client, world["b"], sent["id"], "accept")

    assert (await act(client, world["a"], sent["id"], "cancel")).status_code == 409


async def test_an_invitation_cannot_be_answered_from_its_expiry_instant_on(
    client: httpx.AsyncClient, world: dict[str, Any], clock: MutableClock
):
    sent = await send(client, world)
    expires_at = datetime.fromisoformat(sent["expires_at"])

    clock.moment = expires_at - timedelta(seconds=1)
    open_view = await client.get(f"{BASE}/{sent['id']}", headers=world["b"].headers)
    clock.moment = expires_at
    late_accept = await act(client, world["b"], sent["id"], "accept")
    late_cancel = await act(client, world["a"], sent["id"], "cancel")
    expired_view = await client.get(f"{BASE}/{sent['id']}", headers=world["b"].headers)

    assert open_view.json()["status"] == "pending"
    assert late_accept.status_code == 409 and "expired" in late_accept.json()["detail"]
    assert late_cancel.status_code == 409
    assert expired_view.json()["status"] == "expired"
    assert expired_view.json()["sender"]["contact"] is None


async def test_a_new_invitation_is_possible_once_the_old_one_expired(
    client: httpx.AsyncClient, world: dict[str, Any], clock: MutableClock
):
    first = await send(client, world)
    clock.moment = datetime.fromisoformat(first["expires_at"]) + timedelta(seconds=1)

    second = await invite(client, world["a"], world["b_profile"])
    listing = await client.get(BASE, headers=world["a"].headers)

    assert second.status_code == 201
    assert sorted(item["status"] for item in listing.json()) == ["expired", "pending"]


async def test_sending_twice_to_the_same_person_is_a_conflict_until_it_is_settled(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    first = await send(client, world)

    duplicate = await invite(client, world["a"], world["b_profile"])
    await act(client, world["b"], first["id"], "decline")
    again = await invite(client, world["a"], world["b_profile"])

    assert duplicate.status_code == 409
    assert again.status_code == 201


async def test_the_reverse_invitation_is_allowed(client: httpx.AsyncClient, world: dict[str, Any]):
    await send(client, world)

    reverse = await invite(client, world["b"], world["a_profile"])

    assert reverse.status_code == 201


async def test_inviting_yourself_is_a_conflict(client: httpx.AsyncClient, world: dict[str, Any]):
    response = await invite(client, world["a"], world["a_profile"])

    assert response.status_code == 409


async def test_a_hidden_profile_and_a_missing_one_are_both_404_with_the_same_body(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    _, hidden = await sign_up_with_profile(client, is_visible=False)

    hidden_response = await invite(client, world["a"], hidden["id"])
    missing_response = await invite(client, world["a"], str(uuid4()))

    assert hidden_response.status_code == missing_response.status_code == 404
    assert hidden_response.json() == missing_response.json()


async def test_the_sender_needs_a_profile(client: httpx.AsyncClient, world: dict[str, Any]):
    no_profile = await sign_up(client)

    response = await invite(client, no_profile, world["b_profile"])

    assert response.status_code == 409


async def test_a_hidden_sender_can_still_invite(client: httpx.AsyncClient, world: dict[str, Any]):
    hidden_sender, _ = await sign_up_with_profile(client, is_visible=False)

    response = await invite(client, hidden_sender, world["b_profile"])

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"recipient_profile_id": "not-a-uuid"},
        {"recipient_profile_id": None},
        {"recipient_profile_id": str(uuid4()), "message": "x" * 281},
        {"recipient_profile_id": str(uuid4()), "message": None},
        {"recipient_profile_id": str(uuid4()), "sender_user_id": str(uuid4())},
        {"recipient_profile_id": str(uuid4()), "status": "accepted"},
    ],
)
async def test_invalid_bodies_are_rejected_without_echoing_input(
    client: httpx.AsyncClient, world: dict[str, Any], body: dict[str, Any]
):
    response = await client.post(BASE, json=body, headers=world["a"].headers)

    assert response.status_code == 422
    assert set(response.json()) == {"detail"}
    for error in response.json()["detail"]:
        assert set(error) == {"type", "loc", "msg"}
    assert "x" * 50 not in response.text


async def test_a_free_text_note_is_refused_and_never_echoed(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    response = await invite(client, world["a"], world["b_profile"], message=MESSAGE)

    assert response.status_code == 422
    assert MESSAGE not in response.text
    listing = await client.get(BASE, headers=world["a"].headers)
    assert listing.json() == []


async def test_a_malformed_invitation_id_is_a_422_not_a_500(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    response = await client.get(f"{BASE}/not-a-uuid", headers=world["a"].headers)

    assert response.status_code == 422


async def test_listing_filters_by_direction_status_and_paginates(
    client: httpx.AsyncClient, world: dict[str, Any], clock: MutableClock
):
    first = await send(client, world)
    clock.moment = T0 + timedelta(minutes=1)
    third = await invite(client, world["c"], world["b_profile"])
    clock.moment = T0 + timedelta(minutes=2)
    await act(client, world["b"], first["id"], "decline")
    clock.moment = T0 + timedelta(minutes=3)
    reverse = await invite(client, world["b"], world["a_profile"])
    headers = world["b"].headers

    incoming = await client.get(BASE, params={"direction": "incoming"}, headers=headers)
    outgoing = await client.get(BASE, params={"direction": "outgoing"}, headers=headers)
    pending = await client.get(BASE, params={"status": "pending"}, headers=headers)
    declined = await client.get(BASE, params={"status": "declined"}, headers=headers)
    page = await client.get(BASE, params={"skip": 1, "limit": 1}, headers=headers)

    assert [i["id"] for i in incoming.json()] == [third.json()["id"], first["id"]]
    assert {i["direction"] for i in incoming.json()} == {"incoming"}
    assert [i["id"] for i in outgoing.json()] == [reverse.json()["id"]]
    assert {i["id"] for i in pending.json()} == {third.json()["id"], reverse.json()["id"]}
    assert [i["id"] for i in declined.json()] == [first["id"]]
    assert [i["id"] for i in page.json()] == [third.json()["id"]]


async def test_listing_shows_a_stale_pending_invitation_as_expired(
    client: httpx.AsyncClient, world: dict[str, Any], clock: MutableClock
):
    sent = await send(client, world)
    clock.moment = datetime.fromisoformat(sent["expires_at"])

    expired = await client.get(BASE, params={"status": "expired"}, headers=world["b"].headers)
    pending = await client.get(BASE, params={"status": "pending"}, headers=world["b"].headers)

    assert [i["id"] for i in expired.json()] == [sent["id"]]
    assert expired.json()[0]["status"] == "expired"
    assert pending.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"direction": "sideways"},
        {"status": "archived"},
        {"skip": -1},
        {"limit": 0},
        {"limit": 101},
    ],
)
async def test_invalid_query_parameters_are_rejected(
    client: httpx.AsyncClient, world: dict[str, Any], params: dict[str, Any]
):
    response = await client.get(BASE, params=params, headers=world["a"].headers)

    assert response.status_code == 422
    assert "sideways" not in response.text and "archived" not in response.text


async def test_deleting_the_sender_account_removes_the_invitation_for_the_recipient(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)

    deleted = await client.delete("/api/v1/auth/me", headers=world["a"].headers)
    listing = await client.get(BASE, headers=world["b"].headers)
    read = await client.get(f"{BASE}/{sent['id']}", headers=world["b"].headers)

    assert deleted.status_code == 204
    assert listing.json() == []
    assert read.status_code == 404


async def test_deleting_the_recipient_account_removes_the_invitation_for_the_sender(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)

    await client.delete("/api/v1/auth/me", headers=world["b"].headers)

    assert (await client.get(BASE, headers=world["a"].headers)).json() == []
    assert (await client.get(f"{BASE}/{sent['id']}", headers=world["a"].headers)).status_code == 404


async def test_deleting_the_partner_profile_leaves_the_invitation_without_a_partner(
    client: httpx.AsyncClient, world: dict[str, Any]
):
    sent = await send(client, world)

    await client.delete("/api/v1/profiles/me", headers=world["a"].headers)
    response = await client.get(f"{BASE}/{sent['id']}", headers=world["b"].headers)

    assert response.status_code == 200
    assert response.json()["sender"] is None


async def test_contacts_and_messages_never_reach_the_logs(
    client: httpx.AsyncClient,
    world: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    capfd: pytest.CaptureFixture[str],
):
    caplog.set_level(logging.DEBUG)
    sent = await send(client, world)
    await client.get(BASE, headers=world["b"].headers)
    await act(client, world["b"], sent["id"], "accept")
    await invite(client, world["a"], world["b_profile"], message=MESSAGE * 20)
    # Refused attempts of a user without a contact must not log anything private either
    await invite(client, world["n"], world["a_profile"])
    pending_for_n = await invite(client, world["c"], world["n_profile"])
    await act(client, world["n"], pending_for_n.json()["id"], "accept")

    records = " ".join(f"{record.getMessage()} {vars(record)}" for record in caplog.records)
    streams = capfd.readouterr()
    haystack = f"{caplog.text} {records} {streams.out} {streams.err}"

    for canary in (SENDER_CONTACT, RECIPIENT_CONTACT, OUTSIDER_CONTACT, MESSAGE):
        assert canary not in haystack
    assert "request" in haystack
