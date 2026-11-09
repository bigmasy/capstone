from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.errors import AccessDeniedError, ConflictError, NotFoundError
from app.domain.invitations import CONTACT_REQUIRED_MESSAGE, ContactRequiredError, Direction, Status
from app.services.invitations import InvitationService
from tests.unit.services.fakes_invitations import FakeInvitations, FakeProfiles

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
TTL_DAYS = 14


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


@pytest.fixture
def clock() -> Clock:
    return Clock(T0)


@pytest.fixture
def invitations() -> FakeInvitations:
    return FakeInvitations()


@pytest.fixture
def profiles() -> FakeProfiles:
    return FakeProfiles()


@pytest.fixture
def service(
    invitations: FakeInvitations, profiles: FakeProfiles, clock: Clock
) -> InvitationService:
    return InvitationService(invitations, profiles, TTL_DAYS, clock)  # type: ignore[arg-type]


@pytest.fixture
def sender(profiles: FakeProfiles):
    user_id = uuid4()
    profiles.add(user_id)
    return user_id


@pytest.fixture
def recipient(profiles: FakeProfiles):
    user_id = uuid4()
    profile_id = profiles.add(user_id)
    return user_id, profile_id


async def test_create_stamps_the_expiry_from_the_setting(
    service: InvitationService, invitations: FakeInvitations, sender, recipient
):
    recipient_user, recipient_profile = recipient

    view = await service.create_invitation(sender, recipient_profile)

    _, to_user, created, expires = invitations.created[0]
    assert to_user == recipient_user
    assert created == T0
    assert expires == T0 + timedelta(days=TTL_DAYS)
    assert view.invitation.status is Status.PENDING
    assert view.partner_contact is None


async def test_create_needs_a_profile_of_the_sender(
    service: InvitationService, invitations: FakeInvitations, recipient
):
    with pytest.raises(ConflictError):
        await service.create_invitation(uuid4(), recipient[1])

    assert invitations.created == []


async def test_a_hidden_profile_and_a_missing_one_look_the_same(
    service: InvitationService, profiles: FakeProfiles, sender
):
    hidden = profiles.add(uuid4(), visible=False)

    with pytest.raises(NotFoundError) as hidden_error:
        await service.create_invitation(sender, hidden)
    with pytest.raises(NotFoundError) as missing_error:
        await service.create_invitation(sender, uuid4())

    assert hidden_error.value.message == missing_error.value.message


async def test_a_user_cannot_invite_themselves(
    service: InvitationService, profiles: FakeProfiles, invitations: FakeInvitations
):
    user = uuid4()
    own_profile = profiles.add(user)

    with pytest.raises(ConflictError):
        await service.create_invitation(user, own_profile)

    assert invitations.created == []


async def test_a_duplicate_pending_invitation_is_a_conflict(
    service: InvitationService, sender, recipient
):
    await service.create_invitation(sender, recipient[1])

    with pytest.raises(ConflictError):
        await service.create_invitation(sender, recipient[1])


async def test_the_recipient_accepts_and_the_contact_is_released(
    service: InvitationService, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])

    accepted = await service.accept_invitation(created.invitation.id, recipient[0])

    assert accepted.invitation.status is Status.ACCEPTED
    assert accepted.invitation.responded_at == T0
    assert accepted.partner_contact == "partner-contact"


async def test_the_recipient_declines(service: InvitationService, sender, recipient):
    created = await service.create_invitation(sender, recipient[1])

    declined = await service.decline_invitation(created.invitation.id, recipient[0])

    assert declined.invitation.status is Status.DECLINED
    assert declined.partner_contact is None


async def test_the_sender_cancels(service: InvitationService, sender, recipient):
    created = await service.create_invitation(sender, recipient[1])

    cancelled = await service.cancel_invitation(created.invitation.id, sender)

    assert cancelled.invitation.status is Status.CANCELLED


async def test_an_outsider_gets_not_found_for_every_action(
    service: InvitationService, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])
    outsider = uuid4()

    for call in (service.accept_invitation, service.decline_invitation, service.cancel_invitation):
        with pytest.raises(NotFoundError):
            await call(created.invitation.id, outsider)
    with pytest.raises(NotFoundError):
        await service.get_invitation(created.invitation.id, outsider)


async def test_a_missing_invitation_and_a_foreign_one_have_the_same_message(
    service: InvitationService, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])

    with pytest.raises(NotFoundError) as foreign:
        await service.get_invitation(created.invitation.id, uuid4())
    with pytest.raises(NotFoundError) as missing:
        await service.get_invitation(uuid4(), sender)

    assert foreign.value.message == missing.value.message


@pytest.mark.parametrize(
    ("action", "wrong_party"),
    [
        ("accept_invitation", "sender"),
        ("decline_invitation", "sender"),
        ("cancel_invitation", "recipient"),
    ],
)
async def test_the_wrong_party_is_forbidden(
    service: InvitationService, sender, recipient, action: str, wrong_party: str
):
    created = await service.create_invitation(sender, recipient[1])
    actor = sender if wrong_party == "sender" else recipient[0]

    with pytest.raises(AccessDeniedError):
        await getattr(service, action)(created.invitation.id, actor)


async def test_the_role_is_checked_before_the_state(service: InvitationService, sender, recipient):
    created = await service.create_invitation(sender, recipient[1])
    await service.cancel_invitation(created.invitation.id, sender)

    # The sender may not accept, whatever the state; the state is not revealed
    with pytest.raises(AccessDeniedError):
        await service.accept_invitation(created.invitation.id, sender)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("accept_invitation", "decline_invitation"),
        ("accept_invitation", "accept_invitation"),
        ("decline_invitation", "accept_invitation"),
    ],
)
async def test_an_answered_invitation_cannot_be_answered_again(
    service: InvitationService, sender, recipient, first: str, second: str
):
    created = await service.create_invitation(sender, recipient[1])
    await getattr(service, first)(created.invitation.id, recipient[0])

    with pytest.raises(ConflictError):
        await getattr(service, second)(created.invitation.id, recipient[0])


async def test_a_cancelled_invitation_cannot_be_accepted(
    service: InvitationService, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])
    await service.cancel_invitation(created.invitation.id, sender)

    with pytest.raises(ConflictError):
        await service.accept_invitation(created.invitation.id, recipient[0])


async def test_an_expired_invitation_cannot_be_answered_from_the_expiry_instant_on(
    service: InvitationService, clock: Clock, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])
    expires_at = created.invitation.expires_at

    clock.moment = expires_at - timedelta(microseconds=1)
    still_open = await service.get_invitation(created.invitation.id, recipient[0])
    clock.moment = expires_at
    with pytest.raises(ConflictError, match="expired"):
        await service.accept_invitation(created.invitation.id, recipient[0])
    with pytest.raises(ConflictError, match="expired"):
        await service.cancel_invitation(created.invitation.id, sender)

    assert still_open.invitation.status is Status.PENDING
    reported = await service.get_invitation(created.invitation.id, recipient[0])
    assert reported.invitation.status is Status.EXPIRED


async def test_the_listing_reports_a_stale_pending_invitation_as_expired(
    service: InvitationService, clock: Clock, sender, recipient
):
    await service.create_invitation(sender, recipient[1])
    clock.moment = T0 + timedelta(days=TTL_DAYS)

    listed = await service.get_invitations(sender, Direction.OUTGOING, None, 0, 10)

    assert [view.invitation.status for view in listed] == [Status.EXPIRED]


async def test_losing_a_race_is_reported_as_a_conflict(
    service: InvitationService, invitations: FakeInvitations, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])

    async def other_request_wins() -> None:
        await invitations.decline_invitation(created.invitation.id, recipient[0], T0)

    invitations.before_write = other_request_wins

    with pytest.raises(ConflictError, match="no longer pending"):
        await service.accept_invitation(created.invitation.id, recipient[0])

    assert invitations.records[created.invitation.id].status is Status.DECLINED


async def test_losing_a_race_to_a_deletion_is_not_found(
    service: InvitationService, invitations: FakeInvitations, sender, recipient
):
    created = await service.create_invitation(sender, recipient[1])

    async def invitation_disappears() -> None:
        invitations.records.pop(created.invitation.id)

    invitations.before_write = invitation_disappears

    with pytest.raises(NotFoundError):
        await service.accept_invitation(created.invitation.id, recipient[0])


async def test_the_listing_passes_the_filters_through(
    service: InvitationService, profiles: FakeProfiles, sender, recipient
):
    await service.create_invitation(sender, recipient[1])
    third_user = uuid4()
    profiles.add(third_user)
    sender_profile = next(pid for pid, uid in profiles.owners.items() if uid == sender)
    await service.create_invitation(third_user, sender_profile)

    outgoing = await service.get_invitations(sender, Direction.OUTGOING, None, 0, 10)
    incoming = await service.get_invitations(sender, Direction.INCOMING, None, 0, 10)
    everything = await service.get_invitations(sender, None, None, 0, 10)
    paged = await service.get_invitations(sender, None, None, 1, 10)

    assert (len(outgoing), len(incoming), len(everything), len(paged)) == (1, 1, 2, 1)


async def test_sending_needs_a_contact_on_the_senders_profile(
    service: InvitationService, profiles: FakeProfiles, invitations: FakeInvitations, recipient
):
    no_contact = uuid4()
    profiles.add(no_contact, contact=False)

    with pytest.raises(ContactRequiredError) as error:
        await service.create_invitation(no_contact, recipient[1])

    assert error.value.message == CONTACT_REQUIRED_MESSAGE
    assert isinstance(error.value, ConflictError)
    assert invitations.created == []


async def test_the_contact_rule_does_not_reveal_whether_the_target_exists(
    service: InvitationService, profiles: FakeProfiles
):
    no_contact = uuid4()
    profiles.add(no_contact, contact=False)
    hidden = profiles.add(uuid4(), visible=False)

    # The check concerns only the caller, so a hidden and a missing profile still look equal
    for target in (hidden, uuid4()):
        with pytest.raises(ContactRequiredError):
            await service.create_invitation(no_contact, target)


async def test_a_sender_without_a_profile_is_told_to_create_one_not_to_add_a_contact(
    service: InvitationService, recipient
):
    with pytest.raises(ConflictError) as error:
        await service.create_invitation(uuid4(), recipient[1])

    assert not isinstance(error.value, ContactRequiredError)


async def test_accepting_needs_a_contact_on_the_recipients_profile(
    service: InvitationService, profiles: FakeProfiles, invitations: FakeInvitations, sender
):
    no_contact = uuid4()
    profiles.add(no_contact, contact=False)
    created = await invitations.create_invitation(sender, no_contact, T0, T0 + timedelta(days=1))

    with pytest.raises(ContactRequiredError):
        await service.accept_invitation(created.id, no_contact)

    assert invitations.records[created.id].status is Status.PENDING


async def test_declining_and_cancelling_do_not_need_a_contact(
    service: InvitationService, profiles: FakeProfiles, invitations: FakeInvitations, sender
):
    no_contact = uuid4()
    profiles.add(no_contact, contact=False)
    first = await invitations.create_invitation(sender, no_contact, T0, T0 + timedelta(days=1))

    declined = await service.decline_invitation(first.id, no_contact)

    assert declined.invitation.status is Status.DECLINED


async def test_the_contact_rule_comes_after_the_not_found_forbidden_and_conflict_checks(
    service: InvitationService, profiles: FakeProfiles, invitations: FakeInvitations, sender
):
    no_contact = uuid4()
    profiles.add(no_contact, contact=False)
    created = await invitations.create_invitation(sender, no_contact, T0, T0 + timedelta(days=1))
    sender_without_contact = uuid4()
    profiles.add(sender_without_contact, contact=False)
    foreign = await invitations.create_invitation(
        sender_without_contact, uuid4(), T0, T0 + timedelta(days=1)
    )

    with pytest.raises(NotFoundError):
        await service.accept_invitation(created.id, uuid4())
    with pytest.raises(NotFoundError):
        await service.accept_invitation(foreign.id, no_contact)
    with pytest.raises(AccessDeniedError):
        await service.accept_invitation(foreign.id, sender_without_contact)
    await service.decline_invitation(created.id, no_contact)
    with pytest.raises(ConflictError) as error:
        await service.accept_invitation(created.id, no_contact)

    assert not isinstance(error.value, ContactRequiredError)
