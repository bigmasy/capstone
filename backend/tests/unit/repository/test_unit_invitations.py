import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database.db import enable_sqlite_foreign_keys
from app.database.models import Base, Invitation
from app.domain.account import ProfileRecord
from app.domain.errors import ConflictError, NotFoundError
from app.domain.invitations import Direction, InvitationView, Role, Status
from app.domain.privacy import GridCell
from app.domain.profile import SportEntry
from app.domain.taxonomy import DistrictCode, SkillLevel, SportCode
from app.repository.invitations import InvitationRepository
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
EXPIRES = NOW + timedelta(days=14)


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def invitations(session: AsyncSession) -> InvitationRepository:
    return InvitationRepository(session)


async def make_user(session: AsyncSession, contact: str | None = None, **overrides: object) -> UUID:
    """Create a user with a profile; the profile holds the contact, if any."""
    account = await UserRepository(session).create_user(f"{uuid4().hex}@example.org", "hash")
    values: dict[str, object] = {
        "display_name": "Orest",
        "district": DistrictCode.KYIV_PODILSKYI,
        "intensity": 3,
        "is_visible": True,
        "cell": GridCell(latitude=50.46, longitude=30.51),
        "sports": (
            SportEntry(SportCode.SWIMMING, SkillLevel.INTERMEDIATE),
            SportEntry(SportCode.ARCHERY, SkillLevel.BEGINNER),
        ),
        "capabilities": (),
        "functional_consent_at": None,
        "contact": contact,
    }
    values.update(overrides)
    await ProfileRepository(session).replace_profile(account.id, ProfileRecord(**values))  # type: ignore[arg-type]
    return account.id


async def make_users(session: AsyncSession, count: int) -> list[UUID]:
    return [await make_user(session) for _ in range(count)]


async def invite(
    repo: InvitationRepository, sender: UUID, recipient: UUID, **overrides: object
) -> UUID:
    values: dict[str, object] = {"now": NOW, "expires_at": EXPIRES}
    values.update(overrides)
    record = await repo.create_invitation(sender, recipient, **values)  # type: ignore[arg-type]
    return record.id


async def status_in_storage(session: AsyncSession, invitation_id: UUID) -> Status:
    row = (
        await session.execute(
            select(Invitation.status)
            .where(Invitation.id == invitation_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return row


async def test_create_returns_a_pending_record_with_utc_times(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)

    record = await invitations.create_invitation(sender, recipient, NOW, EXPIRES)

    assert record.status is Status.PENDING
    assert (record.sender_user_id, record.recipient_user_id) == (sender, recipient)
    assert record.created_at == NOW and record.expires_at == EXPIRES
    assert record.created_at.tzinfo is not None
    assert record.responded_at is None


async def test_create_is_committed_before_the_method_returns(
    engine: AsyncEngine, session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)

    await invite(invitations, sender, recipient)

    async with async_sessionmaker(engine)() as other:
        assert await other.scalar(select(func.count()).select_from(Invitation)) == 1


async def test_a_second_pending_invitation_for_the_pair_is_a_conflict(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    await invite(invitations, sender, recipient)

    with pytest.raises(ConflictError):
        await invite(invitations, sender, recipient)

    assert await session.scalar(select(func.count()).select_from(Invitation)) == 1


async def test_a_stale_pending_invitation_is_retired_when_the_pair_is_invited_again(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    first = await invite(invitations, sender, recipient)
    later = EXPIRES + timedelta(seconds=1)

    second = await invite(
        invitations, sender, recipient, now=later, expires_at=later + timedelta(days=14)
    )

    assert await status_in_storage(session, first) is Status.EXPIRED
    assert await status_in_storage(session, second) is Status.PENDING


async def test_a_pending_invitation_exactly_at_its_expiry_is_already_stale(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    await invite(invitations, sender, recipient)

    await invite(
        invitations, sender, recipient, now=EXPIRES, expires_at=EXPIRES + timedelta(days=1)
    )


async def test_a_settled_invitation_does_not_block_a_new_one(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    first = await invite(invitations, sender, recipient)
    await invitations.decline_invitation(first, recipient, NOW)

    await invite(invitations, sender, recipient)


async def test_inviting_a_user_that_does_not_exist_is_not_found(
    session: AsyncSession, invitations: InvitationRepository
):
    sender = await make_user(session)

    with pytest.raises(NotFoundError):
        await invite(invitations, sender, uuid4())


async def test_a_participant_can_load_the_invitation_with_the_other_party(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session, display_name="Recipient")
    invitation_id = await invite(invitations, sender, recipient)

    as_sender = await invitations.get_invitation_by_id(invitation_id, sender)
    as_recipient = await invitations.get_invitation_by_id(invitation_id, recipient)

    assert as_sender is not None and as_recipient is not None
    assert as_sender.role is Role.SENDER and as_recipient.role is Role.RECIPIENT
    assert as_sender.partner is not None and as_sender.partner.display_name == "Recipient"
    assert as_recipient.partner is not None and as_recipient.partner.display_name == "Orest"
    assert [entry.sport for entry in as_sender.partner.sports] == [
        SportCode.ARCHERY,
        SportCode.SWIMMING,
    ]


async def test_a_foreign_or_missing_invitation_is_none(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient, outsider = await make_users(session, 3)
    invitation_id = await invite(invitations, sender, recipient)

    assert await invitations.get_invitation_by_id(invitation_id, outsider) is None
    assert await invitations.get_invitation_by_id(uuid4(), sender) is None


async def test_the_contact_is_withheld_until_the_invitation_is_accepted(
    session: AsyncSession, invitations: InvitationRepository
):
    sender = await make_user(session, contact="sender-contact")
    recipient = await make_user(session, contact="recipient-contact")
    invitation_id = await invite(invitations, sender, recipient)

    pending_for_recipient = await invitations.get_invitation_by_id(invitation_id, recipient)
    pending_for_sender = await invitations.get_invitation_by_id(invitation_id, sender)
    await invitations.accept_invitation(invitation_id, recipient, NOW)
    accepted_for_recipient = await invitations.get_invitation_by_id(invitation_id, recipient)
    accepted_for_sender = await invitations.get_invitation_by_id(invitation_id, sender)

    assert pending_for_recipient is not None and pending_for_sender is not None
    assert pending_for_recipient.partner_contact is None
    assert pending_for_sender.partner_contact is None
    assert accepted_for_recipient is not None and accepted_for_sender is not None
    assert accepted_for_recipient.partner_contact == "sender-contact"
    assert accepted_for_sender.partner_contact == "recipient-contact"


@pytest.mark.parametrize("settle", ["decline", "cancel"])
async def test_the_contact_is_never_released_for_a_settled_but_not_accepted_invitation(
    session: AsyncSession, invitations: InvitationRepository, settle: str
):
    sender = await make_user(session, contact="sender-contact")
    recipient = await make_user(session, contact="recipient-contact")
    invitation_id = await invite(invitations, sender, recipient)
    if settle == "decline":
        await invitations.decline_invitation(invitation_id, recipient, NOW)
    else:
        await invitations.cancel_invitation(invitation_id, sender, NOW)

    views = await invitations.get_invitations(
        sender, None, None, 0, 10, now=NOW
    ) + await invitations.get_invitations(recipient, None, None, 0, 10, now=NOW)

    assert len(views) == 2
    assert all(view.partner_contact is None for view in views)


async def test_accepted_without_a_contact_on_the_profile_gives_none(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session, contact="r")
    invitation_id = await invite(invitations, sender, recipient)
    await invitations.accept_invitation(invitation_id, recipient, NOW)

    as_recipient = await invitations.get_invitation_by_id(invitation_id, recipient)

    assert as_recipient is not None and as_recipient.partner_contact is None


async def test_the_partner_is_none_when_their_profile_is_gone(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    invitation_id = await invite(invitations, sender, recipient)
    await ProfileRepository(session).remove_profile(sender)

    view = await invitations.get_invitation_by_id(invitation_id, recipient)

    assert view is not None and view.partner is None


async def listing(
    repo: InvitationRepository,
    user_id: UUID,
    direction: Direction | None = None,
    status: Status | None = None,
    skip: int = 0,
    limit: int = 50,
    now: datetime = NOW,
) -> list[InvitationView]:
    return await repo.get_invitations(user_id, direction, status, skip, limit, now=now)


async def test_listing_filters_by_direction_and_returns_newest_first(
    session: AsyncSession, invitations: InvitationRepository
):
    me, first, second = await make_users(session, 3)
    older = await invite(invitations, me, first, now=NOW, expires_at=EXPIRES)
    newer = await invite(invitations, me, second, now=NOW + timedelta(hours=1), expires_at=EXPIRES)
    incoming = await invite(
        invitations, first, me, now=NOW + timedelta(hours=2), expires_at=EXPIRES
    )

    outgoing_ids = [v.invitation.id for v in await listing(invitations, me, Direction.OUTGOING)]
    incoming_ids = [v.invitation.id for v in await listing(invitations, me, Direction.INCOMING)]
    both_ids = [v.invitation.id for v in await listing(invitations, me)]

    assert outgoing_ids == [newer, older]
    assert incoming_ids == [incoming]
    assert both_ids == [incoming, newer, older]


async def test_listing_never_includes_other_peoples_invitations(
    session: AsyncSession, invitations: InvitationRepository
):
    me, other, third = await make_users(session, 3)
    await invite(invitations, other, third)

    assert await listing(invitations, me) == []


async def test_listing_paginates(session: AsyncSession, invitations: InvitationRepository):
    me = await make_user(session)
    ids = []
    for hours in range(5):
        recipient = await make_user(session)
        ids.append(
            await invite(
                invitations, me, recipient, now=NOW + timedelta(hours=hours), expires_at=EXPIRES
            )
        )

    page = await listing(invitations, me, skip=1, limit=2)

    assert [view.invitation.id for view in page] == [ids[3], ids[2]]


async def test_listing_by_status_treats_a_stale_pending_invitation_as_expired(
    session: AsyncSession, invitations: InvitationRepository
):
    me, a, b = await make_users(session, 3)
    stale = await invite(invitations, me, a, expires_at=NOW + timedelta(days=1))
    fresh = await invite(invitations, me, b, expires_at=NOW + timedelta(days=30))
    later = NOW + timedelta(days=2)

    pending = await listing(invitations, me, status=Status.PENDING, now=later)
    expired = await listing(invitations, me, status=Status.EXPIRED, now=later)

    assert [v.invitation.id for v in pending] == [fresh]
    assert [v.invitation.id for v in expired] == [stale]


async def test_listing_by_a_settled_status(
    session: AsyncSession, invitations: InvitationRepository
):
    me, a, b = await make_users(session, 3)
    accepted = await invite(invitations, a, me)
    await invite(invitations, b, me)
    await invitations.accept_invitation(accepted, me, NOW)

    result = await listing(invitations, me, Direction.INCOMING, Status.ACCEPTED)

    assert [v.invitation.id for v in result] == [accepted]


@pytest.mark.parametrize(
    ("method", "actor", "expected"),
    [
        ("accept_invitation", "recipient", Status.ACCEPTED),
        ("decline_invitation", "recipient", Status.DECLINED),
        ("cancel_invitation", "sender", Status.CANCELLED),
    ],
)
async def test_a_transition_updates_status_and_response_time(
    session: AsyncSession,
    invitations: InvitationRepository,
    method: str,
    actor: str,
    expected: Status,
):
    sender, recipient = await make_user(session), await make_user(session)
    invitation_id = await invite(invitations, sender, recipient)
    answered_at = NOW + timedelta(hours=3)

    changed = await getattr(invitations, method)(
        invitation_id, sender if actor == "sender" else recipient, answered_at
    )

    assert changed is True
    view = await invitations.get_invitation_by_id(invitation_id, sender)
    assert view is not None
    assert view.invitation.status is expected
    assert view.invitation.responded_at == answered_at


@pytest.mark.parametrize(
    ("method", "wrong_actor"),
    [
        ("accept_invitation", "sender"),
        ("decline_invitation", "sender"),
        ("cancel_invitation", "recipient"),
        ("accept_invitation", "outsider"),
        ("cancel_invitation", "outsider"),
    ],
)
async def test_the_wrong_party_changes_nothing(
    session: AsyncSession, invitations: InvitationRepository, method: str, wrong_actor: str
):
    sender, recipient, outsider = await make_users(session, 3)
    invitation_id = await invite(invitations, sender, recipient)
    actor = {"sender": sender, "recipient": recipient, "outsider": outsider}[wrong_actor]

    changed = await getattr(invitations, method)(invitation_id, actor, NOW)

    assert changed is False
    assert await status_in_storage(session, invitation_id) is Status.PENDING


async def test_a_settled_invitation_cannot_be_changed_again(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    invitation_id = await invite(invitations, sender, recipient)
    assert await invitations.accept_invitation(invitation_id, recipient, NOW) is True

    assert await invitations.decline_invitation(invitation_id, recipient, NOW) is False
    assert await invitations.cancel_invitation(invitation_id, sender, NOW) is False
    assert await invitations.accept_invitation(invitation_id, recipient, NOW) is False
    assert await status_in_storage(session, invitation_id) is Status.ACCEPTED


async def test_answering_at_the_expiry_instant_fails_but_a_moment_earlier_succeeds(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, first, second = await make_users(session, 3)
    at_expiry = await invite(invitations, sender, first)
    just_before = await invite(invitations, sender, second)

    assert await invitations.accept_invitation(at_expiry, first, EXPIRES) is False
    assert (
        await invitations.accept_invitation(
            just_before, second, EXPIRES - timedelta(microseconds=1)
        )
        is True
    )
    assert await status_in_storage(session, at_expiry) is Status.PENDING


async def test_deleting_a_user_removes_their_invitations(
    session: AsyncSession, invitations: InvitationRepository
):
    sender, recipient = await make_user(session), await make_user(session)
    await invite(invitations, sender, recipient)

    await UserRepository(session).remove_user(recipient)

    assert await session.scalar(select(func.count()).select_from(Invitation)) == 0


@pytest.fixture
async def file_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """A file-backed SQLite engine, so that two sessions use two real connections."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'race.db'}")
    enable_sqlite_foreign_keys(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.parametrize("racers", [2, 5])
async def test_simultaneous_accepts_leave_exactly_one_winner(file_engine: AsyncEngine, racers: int):
    maker = async_sessionmaker(file_engine, expire_on_commit=False)
    async with maker() as setup:
        sender, recipient = await make_user(setup), await make_user(setup)
        invitation_id = await invite(InvitationRepository(setup), sender, recipient)

    async def attempt() -> bool:
        async with maker() as own_session:
            return await InvitationRepository(own_session).accept_invitation(
                invitation_id, recipient, NOW
            )

    results = await asyncio.gather(*(attempt() for _ in range(racers)))

    assert sorted(results) == [False] * (racers - 1) + [True]
    async with maker() as check:
        assert await status_in_storage(check, invitation_id) is Status.ACCEPTED


async def test_accept_and_decline_racing_leave_one_outcome(file_engine: AsyncEngine):
    maker = async_sessionmaker(file_engine, expire_on_commit=False)
    async with maker() as setup:
        sender, recipient = await make_user(setup), await make_user(setup)
        invitation_id = await invite(InvitationRepository(setup), sender, recipient)

    async def accept() -> bool:
        async with maker() as own_session:
            return await InvitationRepository(own_session).accept_invitation(
                invitation_id, recipient, NOW
            )

    async def decline() -> bool:
        async with maker() as own_session:
            return await InvitationRepository(own_session).decline_invitation(
                invitation_id, recipient, NOW
            )

    accepted, declined = await asyncio.gather(accept(), decline())

    assert accepted != declined
    async with maker() as check:
        stored = await status_in_storage(check, invitation_id)
    assert stored is (Status.ACCEPTED if accepted else Status.DECLINED)


async def test_simultaneous_invitations_for_one_pair_leave_one_pending(file_engine: AsyncEngine):
    maker = async_sessionmaker(file_engine, expire_on_commit=False)
    async with maker() as setup:
        sender, recipient = await make_user(setup), await make_user(setup)

    async def send() -> bool:
        async with maker() as own_session:
            try:
                await invite(InvitationRepository(own_session), sender, recipient)
            except ConflictError:
                return False
            return True

    results = await asyncio.gather(*(send() for _ in range(4)))

    assert sorted(results) == [False, False, False, True]
